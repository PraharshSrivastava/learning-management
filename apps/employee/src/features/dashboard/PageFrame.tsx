import type { ReactNode } from 'react'

/** Flutter `_SimplePageFrame`: padded scroll page with a title block. */
export function PageFrame({
  title,
  subtitle,
  children,
}: {
  title: string
  subtitle: string
  children: ReactNode
}) {
  return (
    <div className="h-full overflow-y-auto p-6 [scrollbar-width:none]">
      <div className="mx-auto max-w-[1480px]">
        <PageTitle title={title} subtitle={subtitle} />
        {children}
      </div>
    </div>
  )
}

export function PageTitle({ title, subtitle }: { title: string; subtitle: string }) {
  return (
    <div className="mb-6">
      <h1 className="m-0 text-[30px] font-bold text-[#101828]">{title}</h1>
      <p className="m-0 mt-1.5 text-[15px] text-[#667085]">{subtitle}</p>
    </div>
  )
}
