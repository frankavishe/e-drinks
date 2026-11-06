import { useMutation, useQuery, useQueryClient, type QueryKey } from '@tanstack/react-query'
import { getMe } from '../../lib/adminApi'

/**
 * False until the role is known, so edit controls never flash for staff.
 * This only decides what to show: the server refuses staff writes either way.
 */
export function useIsOwner(): boolean {
  const me = useQuery({ queryKey: ['admin', 'me'], queryFn: getMe, retry: false })
  return me.data?.role === 'owner'
}

/**
 * A write to the catalog, zones or settings. The named lists reload afterwards, and after a refusal too,
 * because being refused may mean the record changed underneath.
 * Keys start with 'admin' so that logging out forgets what was loaded, cost prices included.
 */
export function useCatalogAction<Input = void, Output = unknown>(
  queryKeys: QueryKey[],
  action: (input: Input) => Promise<Output>,
  onDone?: (result: Output) => void,
) {
  const queryClient = useQueryClient()
  const reload = () => queryKeys.forEach((queryKey) => queryClient.invalidateQueries({ queryKey }))
  return useMutation({
    mutationFn: action,
    onSuccess: (result) => {
      onDone?.(result)
      reload()
    },
    onError: reload,
  })
}
