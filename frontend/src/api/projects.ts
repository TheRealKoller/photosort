import { apiFetch } from './client'
import type { ProjectOut } from './types'

export interface CreateProjectPayload {
  name: string
  opencloud_path: string
}

export interface TriggerScanResponse {
  status: string
}

export function listProjects(): Promise<ProjectOut[]> {
  return apiFetch<ProjectOut[]>('/projects')
}

export function createProject(payload: CreateProjectPayload): Promise<ProjectOut> {
  return apiFetch<ProjectOut>('/projects', { method: 'POST', body: payload })
}

export function getProject(id: number): Promise<ProjectOut> {
  return apiFetch<ProjectOut>(`/projects/${id}`)
}

export function triggerScan(id: number): Promise<TriggerScanResponse> {
  return apiFetch<TriggerScanResponse>(`/projects/${id}/scan`, { method: 'POST' })
}

export function triggerScore(id: number): Promise<TriggerScanResponse> {
  return apiFetch<TriggerScanResponse>(`/projects/${id}/score`, { method: 'POST' })
}
