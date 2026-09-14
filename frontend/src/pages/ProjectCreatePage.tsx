import { useState } from 'react'
import type { FormEvent } from 'react'
import { Link, useNavigate } from 'react-router'

import { ApiError } from '../api/client'
import { Alert } from '../components/ui/alert'
import { Button } from '../components/ui/button'
import { Input } from '../components/ui/input'
import { FolderBrowser } from '../components/FolderBrowser'
import { useCreateProjectMutation } from '../hooks/useProjects'

export function ProjectCreatePage() {
  const navigate = useNavigate()
  const [name, setName] = useState('')
  const [selectedPath, setSelectedPath] = useState('')
  const [browseHasError, setBrowseHasError] = useState(false)

  const mutation = useCreateProjectMutation()

  const isNameBlank = name.trim() === ''
  const isSubmitDisabled = isNameBlank || browseHasError || mutation.isPending

  function handleSubmit(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault()
    if (isSubmitDisabled) {
      return
    }
    mutation.mutate(
      { name, opencloud_path: selectedPath },
      {
        onSuccess: (project) => {
          navigate(`/projects/${project.id}`)
        },
      },
    )
  }

  const errorDetail =
    mutation.isError && mutation.error instanceof ApiError ? mutation.error.detail : null
  const isNameConflict =
    mutation.isError && mutation.error instanceof ApiError && mutation.error.status === 409

  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-xl sm:text-2xl">Neues Projekt anlegen</h1>
      {errorDetail && <Alert>{errorDetail}</Alert>}
      {/*
        BREITENBEGRENZUNG AB `lg:`: Mobil laufen Feld, Browser und Aktionszeile ueber die volle
        Breite untereinander. Ab dem Umbruchpunkt steht das Namensfeld auf den Spalten 1-6 und der
        Ordner-Browser auf 1-8; die Spalten 9-12 bleiben leer. Ein rund 950px breites Eingabefeld
        fuer einen Projektnamen ist unbrauchbar, und eine Ordnerliste ueber die volle
        Inhaltsbreite ist eine Wueste aus Weissraum zwischen Name und Dateizahl.
      */}
      <form
        onSubmit={handleSubmit}
        className="flex flex-col gap-4 lg:grid lg:grid-cols-12 lg:gap-x-3"
      >
        <div className="flex flex-col gap-2 lg:col-span-6">
          <label htmlFor="project-name" className="text-xs font-medium text-text-h">
            Name
          </label>
          <Input
            id="project-name"
            name="name"
            type="text"
            required
            aria-invalid={isNameConflict || undefined}
            disabled={mutation.isPending}
            value={name}
            onChange={(event) => setName(event.target.value)}
          />
        </div>

        <div className="lg:col-span-8">
          <FolderBrowser
            value={selectedPath}
            onChange={setSelectedPath}
            onErrorChange={setBrowseHasError}
          />
        </div>

        <div className="flex flex-wrap items-center gap-3 lg:col-span-8">
          <Button type="submit" busy={mutation.isPending} disabled={isSubmitDisabled}>
            {mutation.isPending ? 'Wird angelegt…' : 'Projekt anlegen'}
          </Button>
          <Button asChild variant="ghost">
            <Link to="/">Abbrechen</Link>
          </Button>
        </div>
      </form>
    </div>
  )
}
