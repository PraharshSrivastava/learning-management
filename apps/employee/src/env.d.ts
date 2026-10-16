/// <reference types="vite/client" />

declare const __LMS_PUBLIC_MOUNT__: string

interface ImportMetaEnv {
  /** Optional API base. Relative values resolve inside the public mount. */
  readonly VITE_API_BASE_URL?: string
}
