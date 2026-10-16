"""Owned, revision-bound background operations with durable results/proposals."""

import re
import time
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from uuid import uuid4

from app.core.exceptions import ConflictError, ProviderError
from app.core.settings import settings
from app.document_builder.workflow_model import WorkflowModel
from app.schemas.document_workflow import (
    DraftModule,
    ModuleResponse,
    OperationRequest,
    OutlineResponse,
    SourceReference,
    TextBlock,
    outline_fingerprint,
    validate_selection,
)

executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="document-workflow")
stopping = Event()


class WorkflowJobs:
    def __init__(self, repository, model_factory=lambda: WorkflowModel(settings)):
        self.repository = repository
        self.model_factory = model_factory

    def start(self, draft_id, owner, request):
        current = self.repository.get(draft_id, owner)
        if request.task == "import":
            if (
                request.sourceImport is None
                or request.sourceImport.expectedRevision != request.expectedRevision
            ):
                raise ValueError("Source import must capture the current draft revision")
            if current.content.modules and not request.sourceImport.referenceOnly:
                raise ValueError("Import into an empty draft to avoid overwriting existing work")
        if request.task == "outline" and any(
            not getattr(current.content.metadata, key).strip()
            for key in ("courseName", "courseObjective", "targetAudience")
        ):
            raise ValueError(
                "Enter a topic, learning objective and audience before generating an outline"
            )
        if request.task == "draft" and current.approvedOutline != outline_fingerprint(
            current.content
        ):
            raise ConflictError("Approve the outline before drafting modules")
        if request.task == "outline" and any(module.blocks for module in current.content.modules):
            raise ConflictError("Outline regeneration cannot overwrite an existing document")
        if request.task == "draft_module":
            module = next((m for m in current.content.modules if m.id == request.moduleId), None)
            if module is None or not module.included:
                raise ValueError("Choose an included module")
            if any(not isinstance(b, TextBlock) or b.text.strip() for b in module.blocks):
                raise ConflictError("Drafting cannot overwrite populated content")
            if (
                not current.content.metadata.targetAudience.strip()
                or not current.content.metadata.courseObjective.strip()
            ):
                raise ValueError(
                    "Add audience and learning goals in Training details before AI drafting"
                )
        if request.task == "edit":
            if request.target is None or not request.instruction.strip():
                raise ValueError("Select text and describe the requested change")
            validate_selection(current.content, request.target)
        if request.task == "answer" and not request.instruction.strip():
            raise ValueError("Enter a source question")
        if request.task in {"revise", "insert"}:
            if not request.instruction.strip():
                raise ValueError("Describe the requested change")
            modules = [
                m
                for m in current.content.modules
                if request.scope == "document" or m.id == request.moduleId
            ]
            if not modules or (request.task == "insert" and len(modules) != 1):
                raise ValueError("Choose a module for this action")
            if request.task == "revise" and request.scope == "selected":
                raise ValueError("Choose module or document scope")
            if request.insertAfter and not any(
                b.id == request.insertAfter for b in modules[0].blocks
            ):
                raise ValueError("Insertion location no longer exists")
        operation, fresh = self.repository.start_operation(draft_id, owner, request)
        if fresh:
            executor.submit(self.run, draft_id, owner, operation["id"])
        return operation

    def run(self, draft_id, owner, operation_id):
        operation = self.repository.operation(draft_id, owner, operation_id)
        request = OperationRequest.model_validate(operation["request"])

        def cancelled():
            return stopping.is_set() or self.repository.operation(draft_id, owner, operation_id)[
                "status"
            ] not in {"queued", "running"}

        try:
            if not self.repository.claim_operation(draft_id, owner, operation_id):
                return
            current = self.repository.get(draft_id, owner)
            if current.revision != request.expectedRevision:
                raise ConflictError("Draft changed before generation started")
            self.repository.update_operation(draft_id, owner, operation_id, status="running")
            if request.task == "import":
                from app.document_builder.import_source import SourceImporter

                last_heartbeat = 0

                def heartbeat():
                    nonlocal last_heartbeat
                    if time.monotonic() - last_heartbeat >= 5:
                        if cancelled():
                            raise ValueError("Source import cancelled")
                        self.repository.update_operation(
                            draft_id,
                            owner,
                            operation_id,
                            progress="Extracting source content for review",
                        )
                        last_heartbeat = time.monotonic()

                SourceImporter(self.repository).load(
                    draft_id, owner, request.sourceImport, operation_id, heartbeat
                )
                return
            model = self.model_factory()
            sources = self.repository.resources(draft_id, owner, "source")
            excerpts = [
                {
                    "sourceId": source["id"],
                    "spanId": span["id"],
                    "location": span["location"],
                    "text": span["text"],
                }
                for source in sources
                for span in source["spans"]
            ]

            def complete(task, context):
                query = (
                    request.instruction + " " + str(context.get("module", context.get("topic", "")))
                )
                terms = set(re.findall(r"\w+", query.casefold()))
                ranked = sorted(
                    excerpts,
                    key=lambda span: len(
                        terms.intersection(re.findall(r"\w+", span["text"].casefold()))
                    ),
                    reverse=True,
                )
                chosen = []
                size = 0
                for span in ranked:
                    if size + len(span["text"]) <= 60000:
                        chosen.append(span)
                        size += len(span["text"])
                refs = [
                    SourceReference(sourceId=item["sourceId"], spanId=item["spanId"])
                    for item in chosen
                ]
                return model.complete(
                    task,
                    metadata=current.content.metadata,
                    settings=current.content.settings,
                    context={
                        **context,
                        "sourceExcerpts": chosen,
                        "evidenceCoverage": "all extracted spans"
                        if len(chosen) == len(excerpts)
                        else "retrieved excerpts only; absence is not proof that the full source lacks a fact",
                    },
                    allowed_references=refs,
                    cancelled=cancelled,
                ).content.model_dump()

            if request.task == "outline":
                result = complete(
                    "outline",
                    {
                        "topic": current.content.metadata.courseName,
                        "instruction": request.instruction,
                    },
                )
            elif request.task == "draft":
                # Valid modules are saved independently; retry skips populated modules.
                for index, module in enumerate(current.content.modules):
                    if not module.included or any(
                        block.type not in {"paragraph", "heading", "scenario", "takeaway"}
                        or block.text.strip()
                        for block in module.blocks
                    ):
                        continue
                    self.repository.update_operation(
                        draft_id,
                        owner,
                        operation_id,
                        progress=f"Drafting module {index + 1} of {len(current.content.modules)}",
                    )
                    result = complete(
                        "module",
                        {
                            "approvedOutline": [
                                {
                                    "title": item.title,
                                    "objective": item.objective,
                                    "sections": item.sections,
                                }
                                for item in current.content.modules
                                if item.included
                            ],
                            "module": {
                                "title": module.title,
                                "objective": module.objective,
                                "sections": module.sections,
                            },
                        },
                    )
                    if cancelled():
                        return
                    updated = current.content.model_copy(deep=True)
                    updated.modules[index].blocks = [
                        TextBlock(id=uuid4().hex, **block) for block in result["blocks"]
                    ]
                    updated.modules[index].status = "ready"
                    updated.modules[index].sourceReferences = [
                        SourceReference.model_validate(ref)
                        for ref in result.get("sourceReferences", [])
                    ]
                    current = self.repository.save_generated(
                        draft_id, owner, current.revision, updated, operation_id
                    )
                self.repository.update_operation(
                    draft_id,
                    owner,
                    operation_id,
                    status="completed",
                    result={"revision": current.revision},
                )
                return
            elif request.task == "edit":
                selected = validate_selection(current.content, request.target)
                module = next(
                    item for item in current.content.modules if item.id == request.target.moduleId
                )
                result = complete(
                    "edit",
                    {
                        "instruction": request.instruction,
                        "selectedText": selected,
                        "module": module.title,
                        "surroundingText": next(
                            b.text for b in module.blocks if b.id == request.target.blockId
                        ),
                    },
                )
                result["originalText"] = selected
            elif request.task == "revise":
                changes = []
                for module in current.content.modules:
                    if request.scope == "document" and not module.included:
                        continue
                    if request.scope != "document" and module.id != request.moduleId:
                        continue
                    texts = [
                        b for b in module.blocks if isinstance(b, TextBlock) and b.text.strip()
                    ]
                    for offset in range(0, len(texts), 20):
                        batch = texts[offset : offset + 20]
                        proposal = complete(
                            "revise",
                            {
                                "instruction": request.instruction,
                                "module": module.title,
                                "originalTexts": [b.text for b in batch],
                            },
                        )
                        if len(proposal["replacements"]) != len(batch):
                            raise ValueError("Model returned an incomplete revision")
                        changes.extend(
                            {
                                "moduleId": module.id,
                                "blockId": b.id,
                                "originalText": b.text,
                                "replacementText": replacement,
                            }
                            for b, replacement in zip(batch, proposal["replacements"], strict=True)
                        )
                if not changes:
                    raise ValueError("This scope has no text to revise")
                result = {
                    "changes": changes,
                    "summary": "Review all proposed text replacements before accepting.",
                }
            elif request.task == "draft_module":
                module = next(m for m in current.content.modules if m.id == request.moduleId)
                result = complete(
                    "module",
                    {
                        "approvedOutline": [
                            {"title": m.title, "objective": m.objective, "sections": m.sections}
                            for m in current.content.modules
                            if m.included
                        ],
                        "module": {
                            "title": module.title,
                            "objective": module.objective,
                            "sections": module.sections,
                        },
                        "instruction": request.instruction,
                    },
                )
            elif request.task == "insert":
                module = next(m for m in current.content.modules if m.id == request.moduleId)
                result = complete(
                    "insert",
                    {
                        "instruction": request.instruction,
                        "module": module.title,
                        "surroundingText": "\n".join(
                            b.text for b in module.blocks if isinstance(b, TextBlock)
                        ),
                    },
                )
            else:
                result = complete("answer", {"question": request.instruction})
            if cancelled():
                return
            if self.repository.get(draft_id, owner).revision != request.expectedRevision:
                raise ConflictError(
                    "Draft changed while the model was responding; regenerate the suggestion"
                )
            self.repository.update_operation(
                draft_id,
                owner,
                operation_id,
                status="completed" if request.task == "answer" else "proposed",
                result=result,
            )
        except (ProviderError, ConflictError, ValueError) as exc:
            self.repository.update_operation(
                draft_id, owner, operation_id, status="failed", error=str(exc)
            )
        except Exception:
            self.repository.update_operation(
                draft_id,
                owner,
                operation_id,
                status="failed",
                error="Document operation failed. Completed modules are saved; retry the remaining task.",
            )

    @staticmethod
    def apply(content, operation):
        request = OperationRequest.model_validate(operation["request"])
        if request.task == "outline":
            if any(module.blocks for module in content.modules):
                raise ConflictError("Outline suggestion cannot overwrite document content")
            content.modules = [
                DraftModule(id=uuid4().hex, **module.model_dump())
                for module in OutlineResponse.model_validate(operation["result"]).modules
            ]
        elif request.task == "draft_module":
            module = next(m for m in content.modules if m.id == request.moduleId)
            if any(not isinstance(b, TextBlock) or b.text.strip() for b in module.blocks):
                raise ConflictError("Drafting cannot overwrite populated content")
            result = ModuleResponse.model_validate(operation["result"])
            module.blocks = [TextBlock(id=uuid4().hex, **b.model_dump()) for b in result.blocks]
            module.sourceReferences = result.sourceReferences
            module.status = "ready"
        elif request.task == "edit":
            target = request.target
            validate_selection(content, target)
            module = next(item for item in content.modules if item.id == target.moduleId)
            block = next(item for item in module.blocks if item.id == target.blockId)
            replacement = operation["result"]["replacementText"]
            delta = len(replacement) - (target.end - target.start)
            marks = []
            for mark in block.marks:
                if mark.end <= target.start:
                    marks.append(mark)
                elif mark.start >= target.end:
                    marks.append(
                        mark.model_copy(
                            update={"start": mark.start + delta, "end": mark.end + delta}
                        )
                    )
                else:
                    if mark.start < target.start:
                        marks.append(mark.model_copy(update={"end": target.start}))
                    if mark.end > target.end:
                        marks.append(
                            mark.model_copy(
                                update={
                                    "start": target.start + len(replacement),
                                    "end": mark.end + delta,
                                }
                            )
                        )
            block.marks = []
            block.text = block.text[: target.start] + replacement + block.text[target.end :]
            block.marks = marks
        elif request.task == "revise":
            for change in operation["result"]["changes"]:
                module = next(m for m in content.modules if m.id == change["moduleId"])
                if request.scope == "document" and not module.included:
                    raise ConflictError(
                        "This suggestion includes an excluded module. Discard it and generate new suggestions."
                    )
                block = next(b for b in module.blocks if b.id == change["blockId"])
                if block.text != change["originalText"]:
                    raise ConflictError("Text changed; regenerate the suggestion")
                block.marks = []
                block.text = change["replacementText"]
        elif request.task == "insert":
            module = next(m for m in content.modules if m.id == request.moduleId)
            position = next(
                (i + 1 for i, b in enumerate(module.blocks) if b.id == request.insertAfter),
                len(module.blocks),
            )
            module.blocks.insert(
                position,
                TextBlock(
                    id=uuid4().hex,
                    type="scenario",
                    text=operation["result"]["replacementText"],
                    sourceReferences=operation["result"].get("sourceReferences", []),
                ),
            )
        else:
            raise ValueError("This operation cannot be accepted as a document edit")
        return type(content).model_validate(content.model_dump())
