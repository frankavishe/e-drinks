import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { postQuote, type QuoteInput } from '../../lib/publicApi'

export const quoteKey = (input: QuoteInput | null) => ['quote', input] as const

/** Every figure the wizard shows comes from here, never from a calculation in the browser. */
export function useQuote(input: QuoteInput | null) {
  return useQuery({
    queryKey: quoteKey(input),
    queryFn: () => postQuote(input!),
    enabled: input !== null,
    retry: false,
    placeholderData: keepPreviousData,
  })
}
