"""Traduccions per a la sincronització federativa (botó + estat)."""

from __future__ import annotations

SYNC_PACKS: dict[str, dict[str, str]] = {
    "ca": {
        "sync_now": "Sincronitza ara",
        "sync_last": "Darrera sincronització federativa",
        "sync_never": "mai",
        "sync_result_ok": "Sincronització feta: {created} nous, {updated} actualitzats, {removed} eliminats.",
        "sync_result_err": "La sincronització ha fallat: {msg}",
    },
    "es": {
        "sync_now": "Sincronizar ahora",
        "sync_last": "Última sincronización federativa",
        "sync_never": "nunca",
        "sync_result_ok": "Sincronización hecha: {created} nuevos, {updated} actualizados, {removed} eliminados.",
        "sync_result_err": "La sincronización ha fallado: {msg}",
    },
    "eu": {
        "sync_now": "Sinkronizatu orain",
        "sync_last": "Azken sinkronizazio federatiboa",
        "sync_never": "inoiz ez",
        "sync_result_ok": "Sinkronizazioa egina: {created} berri, {updated} eguneratuta, {removed} ezabatuta.",
        "sync_result_err": "Sinkronizazioak huts egin du: {msg}",
    },
    "gl": {
        "sync_now": "Sincronizar agora",
        "sync_last": "Última sincronización federativa",
        "sync_never": "nunca",
        "sync_result_ok": "Sincronización feita: {created} novos, {updated} actualizados, {removed} eliminados.",
        "sync_result_err": "A sincronización fallou: {msg}",
    },
    "pt": {
        "sync_now": "Sincronizar agora",
        "sync_last": "Última sincronização federativa",
        "sync_never": "nunca",
        "sync_result_ok": "Sincronização feita: {created} novos, {updated} atualizados, {removed} removidos.",
        "sync_result_err": "A sincronização falhou: {msg}",
    },
    "fr": {
        "sync_now": "Synchroniser maintenant",
        "sync_last": "Dernière synchronisation fédérative",
        "sync_never": "jamais",
        "sync_result_ok": "Synchronisation faite : {created} nouveaux, {updated} mis à jour, {removed} supprimés.",
        "sync_result_err": "La synchronisation a échoué : {msg}",
    },
    "it": {
        "sync_now": "Sincronizza ora",
        "sync_last": "Ultima sincronizzazione federativa",
        "sync_never": "mai",
        "sync_result_ok": "Sincronizzazione fatta: {created} nuovi, {updated} aggiornati, {removed} rimossi.",
        "sync_result_err": "La sincronizzazione è fallita: {msg}",
    },
    "en": {
        "sync_now": "Sync now",
        "sync_last": "Last federation sync",
        "sync_never": "never",
        "sync_result_ok": "Sync done: {created} new, {updated} updated, {removed} removed.",
        "sync_result_err": "Sync failed: {msg}",
    },
    "de": {
        "sync_now": "Jetzt synchronisieren",
        "sync_last": "Letzte Verbandssynchronisierung",
        "sync_never": "nie",
        "sync_result_ok": "Synchronisierung fertig: {created} neu, {updated} aktualisiert, {removed} entfernt.",
        "sync_result_err": "Synchronisierung fehlgeschlagen: {msg}",
    },
}
