import '@testing-library/jest-dom/vitest'
import { configure } from '@testing-library/react'

// A cold run transforms many files at once, so the default 1 s wait for findBy* can time out.
configure({ asyncUtilTimeout: 3000 })
