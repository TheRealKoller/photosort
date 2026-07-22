import { useState } from 'react'
import type { FormEvent } from 'react'
import { Link, useNavigate } from 'react-router'

import { ApiError } from '../api/client'
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
      }
    )
  }

  const errorDetail =
    mutation.isError && mutation.error instanceof ApiError ? mutation.error.detail : null
  const isNameConflict = mutation.isError && mutation.error instanceof ApiError && mutation.error.status === 409

  return (
    <div>
      <h1>Neues Projekt anlegen</h1>
      {errorDetail && <p role="alert">{errorDetail}</p>}
      <form onSubmit={handleSubmit}>
        <div>
          <label htmlFor="project-name">Name</label>
          <input
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

        <FolderBrowser
          value={selectedPath}
          onChange={setSelectedPath}
          onErrorChange={setBrowseHasError}
        />

        <button type="submit" disabled={isSubmitDisabled}>
          {mutation.isPending ? 'Wird angelegt…' : 'Projekt anlegen'}
        </button>
        <Link to="/">Abbrechen</Link>
      </form>
    </div>
  )
}
