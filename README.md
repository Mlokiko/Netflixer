# Netflix Code Bot 🎬

Bot Discorda, który pobiera kody weryfikacyjne Netflixa z Gmaila i publikuje je na Discordzie.

**Licencja:** MIT

---

## Szybki start

### 1. Konfiguracja Bota/aplikacji w panelu discord

1. W [Developer Portal](https://discord.com/developers/applications) utwórz nową aplikację

2. W sekcji **Bot** włącz **Message Content Intent** i skopiuj token (póżniej wkleisz go do `.env`)

3. W sekcji **OAuth2 → URL Generator** dodaj scope `bot` oraz `applications.commands`, nadaj uprawnienia `Send Messages (Wysyłanie wiadomości)` + `Embed Links (Zamieszczanie linków)`

4. Otwórz wygenerowany URL, aby dodać bota na serwer

### 2. Hasło aplikacyjne Google

1. Wejdź na [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)

2. Upewnij się, że masz włączone **uwierzytelnianie dwuskładnikowe (2FA)**

3. Utwórz nowe hasło dla aplikacji (np. `Netflix Bot`)

4. Skopiuj wygenerowane hasło `xxxx xxxx xxxx xxxx`, (póżniej wkleisz je do `.env`)

### 3. Konfiguracja programu

- Sklonuj repozytorium

- Skopiuj plik `.env.example` do `.env` i uzupełnij go:

| Zmienna                        | Opis                                                                                                                                       |
| ------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------ |
| `DISCORD_BOT_TOKEN`            | Token bota z [Discord Developer Portal](https://discord.com/developers/applications)                                                       |
| `EMAIL_ADDRESS`                | Twój adres Gmail                                                                                                                           |
| `EMAIL_APP_PASSWORD`           | Hasło aplikacyjne Google (patrz wyżej)                                                                                                     |
| `POST_DESTINATION`             | Gdzie publikować kod: `channel` (na stałym kanale) lub `interaction` (tam, gdzie użytkownik wpisał komendę) — **domyślnie: `interaction`** |
| `DISCORD_CHANNEL_ID`           | Opcjonalnie — ID kanału (używane gdy `POST_DESTINATION=channel`)                                                                           |
| `NETFLINK_EXPIRY_MINUTES`      | Czas ważności kodu w minutach (domyślnie: 15)                                                                                              |
| `KOD_COOLDOWN_SECONDS`         | Cooldown między użyciami komend `kod` na użytkownika (domyślnie: 10)                                                                       |
| `EMAIL_SUBJECT_TEMPORARY_CODE` | Temat e-maila z kodem tymczasowego dostępu Netflixa — np: `Twój kod tymczasowego dostępu do serwisu Netflix`                               |
| `EMAIL_SUBJECT_LOGIN_CODE`     | Temat e-maila z kodem logowania Netflixa — np. `Netflix: kod logowania`                                                                    |

### 4. Uruchomienie

**Standalone:**

```bash
pip install -r requirements.txt
python bot.py
```

**Docker:**

```bash
docker compose up --build
```

---

## Komendy

| Komenda               | Opis                                                                        |
| --------------------- | --------------------------------------------------------------------------- |
| `/kod-tymczasowy`     | Zwraca link do uzyskania kodu tymczasowego dostępu do Netflix'a             |
| `/kod-logowanie`      | Zwraca kod logowania do Netflix'a                                           |
| `/zmien-gospodarstwo` | Zmienia gospodarstwo domowe (często spotykane przy logowaniu na TV/Konsoli) |
| `/ping`               | Sprawdza, czy bot jest online                                               |
| `/pomoc`              | Lista wszystkich komend                                                     |

---

## Jak bot działa?

Bot przeszukuje skrzynkę Gmail (ostatnie 24h) pod kątem e-maili Netflixa:

- **Kod tymczasowy** (`/kod-tymczasowy`) — wyszukuje e-maile z tematem zgodnym z `EMAIL_SUBJECT_TEMPORARY_CODE`, wyciąga link weryfikacyjny z treści i publikuje go na Discordzie z odliczaniem do wygaśnięcia.
- **Kod logowania** (`/kod-logowanie`) — wyszukuje e-maile z tematem zgodnym z `EMAIL_SUBJECT_LOGIN_CODE`, wyciąga 4-cyfrowy kod z treści i i publikuje go na Discordzie z odliczaniem do wygaśnięcia.

### Gdzie bot publikuje wiadomości?

Ustaw `POST_DESTINATION` w `.env`:

- **`interaction`** (domyślnie) — kod trafia na kanał, gdzie użytkownik wpisał komendę
- **`channel`** — kod trafia na stały kanał określony w `DISCORD_CHANNEL_ID`. Jeśli `DISCORD_CHANNEL_ID` nie jest ustawione, wraca do zachowania z `interaction`.
