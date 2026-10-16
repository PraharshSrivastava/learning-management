/** Card title (titleMedium) with the bodySmall subtitle 4 px below. */
export function CardTitle({ title, subtitle }: { title: string; subtitle: string }) {
  return (
    <>
      <h2 className="m-0 font-manrope text-lg leading-[24.3px] font-bold tracking-normal text-primary-blue">
        {title}
      </h2>
      <p className="m-0 mt-1 text-xs leading-[16.8px] text-gray">{subtitle}</p>
    </>
  )
}
