import { fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it } from 'vitest'
import i18n from '../i18n'
import Layout from './Layout'

function renderLayout() {
  return render(
    <MemoryRouter>
      <Layout />
    </MemoryRouter>,
  )
}

describe('Layout', () => {
  afterEach(() => i18n.changeLanguage('sw'))

  it('shows Swahili navigation by default', () => {
    renderLayout()
    expect(screen.getByRole('link', { name: 'Vifurushi' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Weka oda' })).toBeInTheDocument()
  })

  it('switches to English', () => {
    renderLayout()
    fireEvent.click(screen.getByRole('button', { name: 'English' }))
    expect(screen.getByRole('link', { name: 'Packages' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Kiswahili' })).toBeInTheDocument()
  })
})
