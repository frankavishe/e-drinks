import { useMutation, useQueryClient } from '@tanstack/react-query'
import type { BookingDetail } from '../../lib/adminApi'
import { ApiError } from '../../lib/api'

export const bookingKey = (id: number) => ['admin', 'booking', id]

/**
 * An action on a booking. The server's answer replaces what's on screen; a refusal reloads it,
 * because being refused may mean the booking changed underneath.
 */
export function useBookingAction<Input = void>(
  bookingId: number,
  action: (input: Input) => Promise<BookingDetail>,
  onDone?: (detail: BookingDetail) => void,
) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: action,
    onSuccess: (detail) => {
      queryClient.setQueryData(bookingKey(bookingId), detail)
      queryClient.invalidateQueries({ queryKey: ['admin', 'bookings'] })
      queryClient.invalidateQueries({ queryKey: ['admin', 'overview'] })
      onDone?.(detail)
    },
    onError: () => queryClient.invalidateQueries({ queryKey: bookingKey(bookingId) }),
  })
}

/** Translation keys for an error, most specific first; i18next uses the first that exists. */
export function refusalKeys(error: unknown): string[] {
  const code = error instanceof ApiError ? error.code : undefined
  return code ? [`admin.refusal.${code}`, 'admin.refusal.unknown'] : ['admin.refusal.unknown']
}
