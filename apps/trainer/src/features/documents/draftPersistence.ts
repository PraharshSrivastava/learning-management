import { errorMessage } from '@lms/shared/api/client'
import type { Content, Draft } from './workflow'

type Snapshot = {
  draft: Draft | null
  content: Content
  dirty: boolean
  saving: boolean
  error: string
}
/** One writer owns revision advancement; responses never overwrite newer browser edits. */
export class DraftPersistence {
  private state: Snapshot
  private generation = 0
  private loadEpoch = 0
  private pending: Promise<Draft> | null = null
  private disposed = false
  constructor(
    content: Content,
    private write: (content: Content, draft: Draft | null) => Promise<Draft>,
    private notify: () => void,
  ) {
    this.state = { draft: null, content, dirty: false, saving: false, error: '' }
  }
  snapshot = () => this.state
  isActive = () => !this.disposed
  private update(value: Partial<Snapshot>) {
    if (!this.disposed) {
      this.state = { ...this.state, ...value }
      this.notify()
    }
  }
  load(value: Draft) {
    this.loadEpoch++
    this.generation++
    this.update({ draft: value, content: value.content, dirty: false, error: '' })
  }
  edit(content: Content) {
    this.generation++
    this.update({ content, dirty: true, error: '' })
  }
  async save(): Promise<Draft> {
    if (this.pending) return this.pending
    if (!this.state.dirty && this.state.draft) return this.state.draft
    const generation = this.generation
    const loadEpoch = this.loadEpoch
    const content = this.state.content
    const draft = this.state.draft
    this.update({ saving: true, error: '' })
    this.pending = this.write(content, draft)
      .then((value) => {
        if (!this.disposed && loadEpoch !== this.loadEpoch)
          throw new Error(
            'This save was superseded by a loaded revision. Retry the action on the current document.',
          )
        if (!this.disposed && loadEpoch === this.loadEpoch) {
          if (generation === this.generation)
            this.update({ draft: value, content: value.content, dirty: false })
          else this.update({ draft: value, dirty: true })
        }
        return value
      })
      .catch((error) => {
        if (loadEpoch === this.loadEpoch) this.update({ error: errorMessage(error), dirty: true })
        throw error
      })
      .finally(() => {
        this.pending = null
        this.update({ saving: false })
      })
    return this.pending
  }
  dispose() {
    this.disposed = true
  }
  activate() {
    this.disposed = false
  }
}
