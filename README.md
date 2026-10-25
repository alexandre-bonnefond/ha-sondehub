# SondeHub Radiosondes pour Home Assistant

Intégration personnalisée (compatible HACS) qui suit les radiosondes météo via
l'API publique de [SondeHub](https://sondehub.org) et te prévient quand :

- une sonde **vole** dans un rayon donné autour de chez toi ;
- un **atterrissage est prévu** (ou déjà effectué) près de chez toi.

Données © SondeHub, licence CC BY-SA 2.0.

## Installation

1. Copie `custom_components/sondehub/` dans `<config>/custom_components/`
   (ou ajoute ce dépôt dans HACS comme dépôt personnalisé).
2. Redémarre Home Assistant.
3. *Paramètres → Appareils et services → Ajouter une intégration → SondeHub*.
4. (Optionnel) Copie `blueprints/automation/sondehub/notify_sonde.yaml` dans
   `<config>/blueprints/automation/sondehub/` et crée une automation depuis le blueprint.

## Réglages

| Option | Défaut | Rôle |
|---|---|---|
| Rayon d'alerte en vol | 100 km | déclenche `sondehub_sonde_nearby` |
| Rayon d'alerte d'atterrissage | 30 km | déclenche `sondehub_landing_nearby` |
| Rayon de surveillance | 300 km | sondes pour lesquelles on récupère une prédiction |
| Intervalle | 90 s | fréquence d'appel de l'API |

## Entités

- `binary_sensor.*_sonde_nearby` / `*_landing_nearby`
- `sensor.*_nearest_sonde_distance` / `*_nearest_landing_distance` (km, avec attributs : série, fréquence, altitude, cap, coordonnées d'atterrissage…)
- `sensor.*_sondes_in_range`

## Événements

`sondehub_sonde_nearby` et `sondehub_landing_nearby`, une seule fois par sonde.
Champs : `serial`, `type`, `frequency`, `latitude`, `longitude`, `altitude`,
`vertical_speed`, `descending`, `distance_km`, `bearing`, `landing_latitude`,
`landing_longitude`, `landing_distance_km`, `landing_bearing`, `landing_time`,
`landed`, `sondehub_url`, `maps_url`.

## Notes

- L'endpoint `/predictions` est marqué *deprecated* dans le swagger de SondeHub :
  s'il disparaît, seule la partie « atterrissage » sera à adapter (`api.py`).
- Sois raisonnable avec l'intervalle : l'API est partagée par la communauté.
