// Observer include panel state (Flutter _ObserverIncludePanelState).
import { errorDetail } from '@lms/shared/api/client'
import {
  observerSelectionToJson,
  parseObserverConfig,
  parseObserverDepartments,
  paths,
  type ObserverAccess,
  type ObserverConfig,
  type ObserverDepartment,
  type ObserverSelection,
  type Reply,
  type Requester,
} from './api'

export interface ObserverMessage {
  text: string
  /** Success text shows as info; failures and conflicts show as warnings. */
  warning: boolean
}

export interface ObserverState {
  revision: number
  busy: boolean
  dirty: boolean
  message: ObserverMessage | null
  selections: ObserverSelection[]
  departments: ObserverDepartment[]
  effective: Record<string, ObserverAccess>
}

class Expired extends Error {}

const errorText = (error: unknown) => (error instanceof Error ? error.message : String(error))

export const REVISION_CHANGED =
  'Observer configuration changed. Your edits are preserved. Review the saved version before saving; your earlier revision cannot overwrite it.'

export class ObserverStore {
  private state: ObserverState = {
    revision: 0,
    busy: true,
    dirty: false,
    message: null,
    selections: [],
    departments: [],
    effective: {},
  }
  private listeners = new Set<() => void>()
  /** Bumped by each load and finished save, so a stale load reply is dropped. */
  private request = 0
  /** False while the panel is unmounted. Its replies must not change the workspace draft. */
  private mounted = false
  private generation: number | undefined

  constructor(
    private readonly courseId: string,
    private readonly http: Requester,
    private readonly onDraftObservers: (ids: string[]) => void,
  ) {}

  subscribe = (listener: () => void) => {
    this.listeners.add(listener)
    return () => void this.listeners.delete(listener)
  }

  getState = () => this.state

  /** Mount effect of the panel. Returns the unmount cleanup. */
  attach = () => {
    this.mounted = true
    return () => void (this.mounted = false)
  }

  private set(patch: Partial<ObserverState>) {
    this.state = { ...this.state, ...patch }
    for (const listener of this.listeners) listener()
  }

  private notifyDraft() {
    this.onDraftObservers(
      this.state.selections.flatMap((s) =>
        s.observerEmployeeId == null ? [] : [s.observerEmployeeId],
      ),
    )
  }

  private response(reply: Reply): unknown {
    if (reply.status === 401 || reply.status === 403) throw new Expired()
    if (reply.status !== 200) {
      throw new Error(errorDetail(reply.body) ?? 'Unable to update observers')
    }
    return reply.body
  }

  private accept(config: ObserverConfig): Partial<ObserverState> {
    return {
      dirty: false,
      effective: config.effective,
      revision: config.revision,
      selections: config.selections,
    }
  }

  /** First call loads; later calls reload when the workspace generation changes. */
  syncGeneration(generation: number) {
    if (this.generation === undefined) {
      this.generation = generation
      void this.load()
    } else if (this.generation !== generation) {
      this.generation = generation
      void this.load(true)
    }
  }

  async load(preserveDraft = false) {
    const serial = ++this.request
    this.set({ busy: true, message: null })
    try {
      const [configReply, optionsReply] = await Promise.all([
        this.http(paths.observers(this.courseId)),
        this.http(paths.observerOptions),
      ])
      const config = parseObserverConfig(this.response(configReply))
      const departments = parseObserverDepartments(this.response(optionsReply))
      if (serial !== this.request || !this.mounted) return
      if (!preserveDraft || !this.state.dirty) {
        this.set({ ...this.accept(config), departments, busy: false })
      } else {
        this.set({
          effective: config.effective,
          departments,
          busy: false,
          message:
            config.revision !== this.state.revision
              ? { text: REVISION_CHANGED, warning: true }
              : null,
        })
      }
      this.notifyDraft()
    } catch (error) {
      if (serial !== this.request || !this.mounted) return
      if (error instanceof Expired) {
        this.set({
          busy: false,
          selections: [],
          effective: {},
          departments: [],
          dirty: false,
          message: { text: 'Observer access changed. Sign in again.', warning: true },
        })
      } else {
        this.set({ busy: false, message: { text: errorText(error), warning: true } })
      }
    }
  }

  async save(apply = false) {
    const { selections, revision } = this.state
    if (!apply) {
      const ids = new Set(selections.map((s) => s.observerEmployeeId))
      if (
        ids.size !== selections.length ||
        selections.some(
          (s) =>
            s.observerEmployeeId == null ||
            (s.employeeIds.length === 0 && s.departmentIds.length === 0),
        )
      ) {
        this.set({
          message: {
            text: 'Choose each observer once and select at least one employee or department.',
            warning: true,
          },
        })
        return
      }
    }
    this.set({ busy: true, message: null })
    try {
      const reply = apply
        ? await this.http(paths.applyObservers(this.courseId), {
            method: 'POST',
            json: { revision },
          })
        : await this.http(paths.observers(this.courseId), {
            method: 'PUT',
            json: { revision, observers: selections.map(observerSelectionToJson) },
          })
      const config = parseObserverConfig(this.response(reply))
      if (!this.mounted) return
      // The save reply is newer than any load still in flight, so those loads are dropped.
      this.request += 1
      this.set({
        ...this.accept(config),
        busy: false,
        message: {
          text: apply
            ? 'Observer access applied.'
            : 'Saved. Restrictions take effect now; additions need Apply Observers after publication.',
          warning: false,
        },
      })
      this.notifyDraft()
    } catch (error) {
      if (!this.mounted) return
      this.set({
        busy: false,
        message: {
          text:
            error instanceof Expired ? 'Observer access changed. Sign in again.' : errorText(error),
          warning: true,
        },
      })
    }
  }

  private edit(selections: ObserverSelection[]) {
    this.set({ selections, dirty: true })
    this.notifyDraft()
  }

  add(observerId: string) {
    this.edit([
      ...this.state.selections,
      { observerEmployeeId: observerId, employeeIds: [], departmentIds: [] },
    ])
  }

  remove(index: number) {
    this.edit(this.state.selections.filter((_, i) => i !== index))
  }

  update(index: number, patch: Partial<ObserverSelection>) {
    this.edit(this.state.selections.map((s, i) => (i === index ? { ...s, ...patch } : s)))
  }
}
