"""Kullanici hesaplari: kayit, giris, oturum, e-posta dogrulama ve parola sifirlama.

Guven siniri web sunucusudur: `/api/auth/*` uclari yalniz servis anahtariyla
(`X-Admin-Token`) cagrilir ve istemci IP'sini web iletir. Oturum token'i
web'in HttpOnly cerezinde durur; kisisel uclar (`/api/me/*`) onu
`Authorization: Bearer` basligiyla alir.
"""
