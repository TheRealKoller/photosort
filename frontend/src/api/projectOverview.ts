import { apiFetch } from './client'
import type { OverviewSeenOut } from './types'

/*
 * Der Merker "Ablaufübersicht gesehen" der angemeldeten Person. `projectId` ist eine geprüfte
 * Ganzzahl, nie ein Rohwert aus der Adresszeile: Ein Segment wie `1/../..` lenkte den
 * authentifizierten `PUT` sonst auf einen anderen Pfad derselben API.
 */

export function getOverviewSeen(projectId: number): Promise<OverviewSeenOut> {
  return apiFetch<OverviewSeenOut>(`/projects/${projectId}/overview-seen`)
}

export function markOverviewSeen(projectId: number): Promise<void> {
  return apiFetch<void>(`/projects/${projectId}/overview-seen`, { method: 'PUT' })
}
