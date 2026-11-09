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

/**
 * Der Leerzustand eines Eye-Projekts, in dem der Eye-Dienst abgeschaltet ist: ohne Eye-Lauf
 * entsteht kein Entwurf, und der Weg führt zu den Einstellungen. Ein eigener Satz statt des
 * allgemeinen Leertexts, weil hier nicht ein Lauf fehlt, sondern die Voraussetzung dafür.
 */
export const DRAFT_EYE_DISABLED_TEXT =
  'Eye ist in dieser Installation abgeschaltet — ohne Eye-Lauf entsteht kein Album-Entwurf. Die ' +
  'Kategorisierung stellst du in den Projekteinstellungen um.'
