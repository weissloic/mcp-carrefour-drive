# MCP Carrefour Drive

Serveur MCP (Model Context Protocol) pour piloter Carrefour Drive depuis Claude. Utilise SeleniumBase avec Chrome headless + noVNC pour contourner la protection anti-bot.

## Architecture

- **Python + SeleniumBase** (UC mode) — Chrome non détectable
- **Docker** — Chrome tourne dans un conteneur Linux
- **noVNC** — accès visuel au navigateur via `http://localhost:6080/vnc.html`
- **Cookies persistants** — session sauvegardée entre les redémarrages

## Démarrage rapide

```bash
docker compose up -d
```

Puis configurer Claude Desktop (`~/Library/Application Support/Claude/claude_desktop_config.json`) :

```json
{
  "mcpServers": {
    "carrefour-drive": {
      "command": "docker",
      "args": ["exec", "-i", "carrefour-mcp", "python", "-m", "main"],
      "env": {}
    }
  }
}
```

## Connexion

1. Appeler `tool_login` (Dans claude, "Connecte toi à Carrefour") → Chrome s'ouvre dans le conteneur 
2. Ouvrir `http://localhost:6080/vnc.html` sur le poste en local → se connecter manuellement sur carrefour.fr (Ecrire son mail / mdp + valider le captcha)

Les cookies sont persistés dans un volume Docker (`/data/cookies.json`) — la connexion survit aux redémarrages.

## Outils disponibles

### Authentification
| Outil | Description |
|-------|-------------|
| `tool_open_browser` | Ouvre Chrome sur la page de login (visible via noVNC) |
| `tool_save_cookies` | Sauvegarde la session après connexion manuelle |
| `tool_login` | Connexion automatique (si identifiants configurés) |
| `tool_check_login` | Vérifie l'état de connexion |
| `tool_logout` | Déconnexion |

### Magasin & livraison
| Outil | Description |
|-------|-------------|
| `tool_select_store` | Sélectionner un magasin Drive par code postal |
| `tool_set_delivery_mode` | Mode : `drive`, `delivery`, ou `express` |

### Recherche
| Outil | Description |
|-------|-------------|
| `tool_search_products` | Chercher des produits (retourne liste avec prix/ID) |
| `tool_search_and_add` | Chercher un produit et l'ajouter au panier |

### Panier
| Outil | Description |
|-------|-------------|
| `tool_get_cart` | Voir le contenu du panier |
| `tool_add_to_cart` | Ajouter un produit par ID |
| `tool_remove_from_cart` | Retirer un produit |
| `tool_update_cart_quantity` | Modifier la quantité |
| `tool_add_shopping_list` | Ajouter une liste d'articles en une fois |

### Créneaux
| Outil | Description |
|-------|-------------|
| `tool_get_available_slots` | Créneaux de retrait disponibles |
| `tool_select_slot` | Réserver un créneau |

### Favoris
| Outil | Description |
|-------|-------------|
| `tool_list_favorites` | Lister les favoris |
| `tool_add_favorite` | Ajouter un favori |
| `tool_remove_favorite` | Supprimer un favori |

### Commandes
| Outil | Description |
|-------|-------------|
| `tool_get_order_history` | Historique des commandes |
| `tool_get_order_items` | Détail d'une commande |

### Checkout
| Outil | Description |
|-------|-------------|
| `tool_get_checkout_summary` | Récapitulatif avant paiement |
| `tool_confirm_and_pay` | Confirmer et payer |

### Statut
| Outil | Description |
|-------|-------------|
| `tool_get_status` | Statut global : connexion, panier, prochain créneau |

## Exemple d'utilisation

```
Ajoute 2 bouteilles de lait demi-écrémé et une baguette à mon panier Carrefour Drive
```

Claude appellera `tool_search_and_add` pour chaque article, puis pourra afficher le contenu du panier avec `tool_get_cart`.

## Structure du projet

```
.
├── main.py                  # Serveur MCP (déclaration des outils)
├── src/
│   ├── browser.py           # Gestion Chrome/SeleniumBase + cookies
│   ├── auth.py              # Connexion / session
│   ├── search.py            # Recherche produits (DOM scraping)
│   ├── cart.py              # Panier (DOM + API fetch)
│   ├── store.py             # Sélection magasin (DOM)
│   ├── status.py            # Statut connexion + panier
│   ├── orders.py            # Historique commandes
│   ├── slots.py             # Créneaux de livraison
│   ├── checkout.py          # Paiement
│   ├── delivery.py          # Mode de livraison
│   └── favorites.py        # Favoris (stockage local JSON)
├── Dockerfile
├── docker-compose.yml
├── docker-entrypoint.sh
└── requirements.txt
```

## Notes techniques

- **Anti-bot** : SeleniumBase UC mode + Chrome avec sandbox activé (`cap_add: SYS_ADMIN`)
- **API Carrefour** : les endpoints `/api/*` nécessitent le header `X-Requested-With: XMLHttpRequest`
- **DOM scraping** : la recherche et la sélection de magasin naviguent vraiment dans la page (pas de fetch direct) pour obtenir le contenu SSR
- **noVNC** : port `6080` exposé — accès via `http://localhost:6080/vnc.html`
- **Données persistées** : cookies, favoris et screenshots dans le volume `/data`

## Limitations

- Les sélecteurs CSS peuvent casser si Carrefour modifie son interface
- Pas d'automatisation du paiement (par choix)
- Nécessite un environnement avec Chrome (géré par Docker -> Pour éviter la pollution de sa machine perso)
