/*
 * Die festen Texte rund um den Album-Entwurf, die an mehr als einer Stelle gelten: im
 * Album-Entwurf, in der Endauswahl und in der Ablaufübersicht. Sie stehen hier und nur hier;
 * eine Kopie liefe beim nächsten Umformulieren still auseinander.
 */

/**
 * Der Leerzustand des Entwurfs - nur ein Lauf ohne Events zeigt ihn. Er benennt den fehlenden
 * Schritt und verlinkt ihn.
 */
export const DRAFT_EMPTY_TEXT = 'Noch kein Auswahlvorschlag — führe die Klassifizierung aus.'

/**
 * Der Leerzustand OHNE Cloud-Freigabe - mit Vorrang vor `DRAFT_EMPTY_TEXT`. Er WIEDERHOLT DEN
 * ZUSTIMMUNGSTEXT NICHT: was an die Cloud geht, steht an genau einer Stelle.
 */
export const DRAFT_CLOUD_CONSENT_TEXT =
  'Ohne Cloud-Freigabe entsteht kein Album-Entwurf. Die Freigabe erteilst du in den ' +
  'Projekteinstellungen.'

/** Die Schaltfläche zur Cloud-Freigabe neben `DRAFT_CLOUD_CONSENT_TEXT`. */
export const SETTINGS_LINK_LABEL = 'Zu den Projekteinstellungen'
