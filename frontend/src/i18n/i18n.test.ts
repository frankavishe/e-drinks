import { describe, expect, it } from 'vitest'
import en from './en.json'
import sw from './sw.json'

function keys(value: object, prefix = ''): string[] {
  return Object.entries(value).flatMap(([key, child]) =>
    typeof child === 'object' ? keys(child, `${prefix}${key}.`) : [`${prefix}${key}`],
  )
}

describe('translations', () => {
  it('have the same keys in Swahili and English', () => {
    expect(keys(sw).sort()).toEqual(keys(en).sort())
  })
})
