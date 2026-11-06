import type { QueryKey } from '@tanstack/react-query'
import { useState, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { primaryClass, secondaryClass } from '../book/ui'
import { Refusal } from './BookingRows'
import { useCatalogAction } from './useCatalogAction'

/** Save and go-back buttons for a form; go-back only when the form can be closed. */
export function FormButtons({
  label,
  pending,
  onCancel,
}: {
  label: string
  pending: boolean
  onCancel?: () => void
}) {
  const { t } = useTranslation()
  return (
    <div className="flex flex-wrap gap-2">
      <button type="submit" className={primaryClass} disabled={pending}>
        {label}
      </button>
      {onCancel && (
        <button type="button" className={secondaryClass} onClick={onCancel}>
          {t('admin.keep')}
        </button>
      )}
    </div>
  )
}

/** Delete, after asking on the page. The server's reason shows if it refuses. */
export function DeleteRecord({
  name,
  queryKeys,
  action,
  afterRefusal,
}: {
  name: string
  queryKeys: QueryKey[]
  action: () => Promise<unknown>
  /** Anything to add when the record is refused for being in use. */
  afterRefusal?: ReactNode
}) {
  const { t } = useTranslation()
  const [asking, setAsking] = useState(false)
  const remove = useCatalogAction(queryKeys, action)
  const label = `${t('admin.manage.delete')}: ${name}`

  if (asking) {
    return (
      <div className="w-full space-y-2">
        <p className="text-sm font-semibold">{t('admin.manage.deleteSure', { name })}</p>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            className={primaryClass}
            disabled={remove.isPending}
            onClick={() => remove.mutate(undefined, { onError: () => setAsking(false) })}
          >
            {t('admin.manage.deleteYes')}
          </button>
          <button type="button" className={secondaryClass} onClick={() => setAsking(false)}>
            {t('admin.keep')}
          </button>
        </div>
      </div>
    )
  }
  return (
    <>
      <button
        type="button"
        aria-label={label}
        className={secondaryClass}
        onClick={() => {
          remove.reset()
          setAsking(true)
        }}
      >
        {t('admin.manage.delete')}
      </button>
      {remove.error != null && (
        <div className="w-full space-y-1">
          <Refusal error={remove.error} />
          {afterRefusal}
        </div>
      )}
    </>
  )
}

/**
 * One record: its details, and for the owner its edit and delete controls.
 * Staff get the details and nothing else.
 */
export function RecordRow({
  name,
  canEdit,
  children,
  queryKeys,
  deleteAction,
  afterRefusal,
  renderForm,
}: {
  name: string
  canEdit: boolean
  children: ReactNode
  queryKeys: QueryKey[]
  deleteAction: () => Promise<unknown>
  afterRefusal?: ReactNode
  renderForm: (close: () => void) => ReactNode
}) {
  const { t } = useTranslation()
  const [editing, setEditing] = useState(false)
  if (editing) return renderForm(() => setEditing(false))
  return (
    <div className="flex flex-wrap items-start gap-x-4 gap-y-2">
      <div className="min-w-0 flex-1 basis-48 break-words">{children}</div>
      {canEdit && (
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            aria-label={`${t('admin.manage.edit')}: ${name}`}
            className={secondaryClass}
            onClick={() => setEditing(true)}
          >
            {t('admin.manage.edit')}
          </button>
          <DeleteRecord name={name} queryKeys={queryKeys} action={deleteAction} afterRefusal={afterRefusal} />
        </div>
      )}
    </div>
  )
}
