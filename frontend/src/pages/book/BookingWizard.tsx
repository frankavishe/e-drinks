import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useEffect, useReducer, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { ApiError } from '../../lib/api'
import { createBooking, type BookingCreated, type BookingInput } from '../../lib/publicApi'
import AddonsStep from './AddonsStep'
import Confirmation from './Confirmation'
import ContactStep, { contactIsComplete } from './ContactStep'
import EventStep from './EventStep'
import OrderStep, { orderIsReady } from './OrderStep'
import ReviewStep, { reviewIsBookable } from './ReviewStep'
import { Notice, primaryClass, secondaryClass } from './ui'
import { quoteKey, useQuote } from './useQuote'
import {
  bookingInput,
  eventIsComplete,
  initialState,
  quoteInput,
  reducer,
  STEPS,
  type ConflictCode,
} from './wizardState'

export default function BookingWizard() {
  const { t, i18n } = useTranslation()
  const queryClient = useQueryClient()
  const [state, dispatch] = useReducer(reducer, initialState)
  const [created, setCreated] = useState<BookingCreated | null>(null)
  const [submitError, setSubmitError] = useState<string | null>(null)
  const heading = useRef<HTMLHeadingElement>(null)
  const name = STEPS[state.step]

  const orderQuote = useQuote(name === 'order' ? quoteInput(state, false) : null)
  const fullInput = name === 'addons' || name === 'review' ? quoteInput(state, true) : null
  const fullQuote = useQuote(fullInput)

  // Moving between steps replaces the whole form, so start the next one from the top.
  const firstRender = useRef(true)
  useEffect(() => {
    if (firstRender.current) {
      firstRender.current = false
      return
    }
    heading.current?.focus()
    window.scrollTo?.({ top: 0 })
  }, [state.step, created])

  const submit = useMutation({
    mutationFn: (input: BookingInput) => createBooking(input),
    onSuccess: setCreated,
    onError: (error) => {
      if (error instanceof ApiError && error.status === 409 && error.code) {
        queryClient.setQueryData(quoteKey(quoteInput(state, true)), error.data?.quote)
        dispatch({ type: 'conflict', code: error.code as ConflictCode })
        return
      }
      if (error instanceof ApiError && error.status === 429) setSubmitError('book.contact.tooMany')
      else if (error instanceof ApiError && error.status === 422) setSubmitError('book.contact.invalid')
      else setSubmitError('book.contact.failed')
    },
  })

  if (created) {
    return (
      <section className="mx-auto max-w-xl px-4 py-8">
        <Confirmation booking={created} />
      </section>
    )
  }

  const nextAllowed = {
    event: eventIsComplete(state),
    order: orderIsReady(orderQuote.data) && !orderQuote.isError && !orderQuote.isFetching,
    addons: !fullQuote.isError && !fullQuote.isFetching && fullQuote.data?.flags.addons_unavailable.length === 0,
    review: reviewIsBookable(fullQuote.data) && !fullQuote.isError && !fullQuote.isFetching,
    contact: contactIsComplete(state) && !submit.isPending,
  }[name]

  function goNext() {
    if (name === 'review') {
      dispatch({ type: 'reviewed', total: fullQuote.data!.total })
    } else if (name === 'contact') {
      setSubmitError(null)
      const input = bookingInput(state, i18n.language)
      if (input) submit.mutate(input)
    } else {
      dispatch({ type: 'goTo', step: state.step + 1 })
    }
  }

  return (
    <section className="mx-auto max-w-xl px-4 py-8">
      <p className="text-sm text-stone-600">
        {t('book.progress', { step: state.step + 1, total: STEPS.length })}
      </p>
      <div className="mt-2 h-1.5 bg-stone-200" aria-hidden="true">
        <div className="h-full bg-emerald-700" style={{ width: `${((state.step + 1) / STEPS.length) * 100}%` }} />
      </div>
      <h1 ref={heading} tabIndex={-1} className="mt-4 mb-5 text-2xl font-bold outline-none">
        {t(`book.${name}.title`)}
      </h1>

      {name === 'event' && <EventStep state={state} dispatch={dispatch} />}
      {name === 'order' && <OrderStep state={state} dispatch={dispatch} />}
      {name === 'addons' && <AddonsStep state={state} dispatch={dispatch} />}
      {name === 'review' && (
        <ReviewStep quote={fullQuote.data} failed={fullQuote.isError} conflict={state.conflict} />
      )}
      {name === 'contact' && <ContactStep state={state} dispatch={dispatch} />}

      {submitError && name === 'contact' && (
        <div className="mt-4">
          <Notice tone="problem">{t(submitError)}</Notice>
        </div>
      )}

      <div className="mt-8 flex justify-between gap-3">
        {state.step > 0 ? (
          <button
            type="button"
            className={secondaryClass}
            onClick={() => dispatch({ type: 'goTo', step: state.step - 1 })}
          >
            {t('book.back')}
          </button>
        ) : (
          <span />
        )}
        <button type="button" className={primaryClass} disabled={!nextAllowed} onClick={goNext}>
          {name === 'contact' ? t('book.contact.submit') : t('book.next')}
        </button>
      </div>
    </section>
  )
}
