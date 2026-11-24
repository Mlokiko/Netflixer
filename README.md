# Netflix Code Bot 🎬

Bot Discorda, który pobiera kody weryfikacyjne Netflixa z Gmaila i publikuje je na Discordzie.

**Licencja:** MIT

---

## Szybki start

### 1. Konfiguracja

```bash
cp .env.example .env
```

Wypełnij dane w `.env`:

| Zmienna                   | Opis                                                                                                        |
| ------------------------- | ----------------------------------------------------------------------------------------------------------- |
| `DISCORD_BOT_TOKEN`       | Token bota z [Discord Developer Portal](https://discord.com/developers/applications)                        |
| `EMAIL_ADDRESS`           | Twój adres Gmail                                                                                            |
| `EMAIL_APP_PASSWORD`      | Hasło aplikacyjne Google (patrz niżej)                                                                      |
| `POST_DESTINATION`        | Gdzie publikować kod: `channel` (na stałym kanale) lub `interaction` (tam, gdzie użytkownik wpisał komendę) — **domyślnie: `interaction`** |
| `DISCORD_CHANNEL_ID`      | Opcjonalnie — ID kanału (używane gdy `POST_DESTINATION=channel`)                                            |
| `NETFLINK_EXPIRY_MINUTES` | Czas ważności kodu w minutach (domyślnie: 15)                                                               |
| `KOD_COOLDOWN_SECONDS`    | Cooldown między użyciami komend na użytkownika, w sekundach (domyślnie: 10)                                 |
| `EMAIL_SUBJECT_CODE`      | Temat e-maila z kodem Netflixa — domyślnie: `Twój kod tymczasowego dostępu do serwisu Netflix`              |
| `EMAIL_SUBJECT_LOGIN_CODE`| Temat e-maila z kodem logowania Netflixa — np. `Netflix: kod logowania`                                     |

### 2. Hasło aplikacyjne Google

1. Wejdź na [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
2. Upewnij się, że masz włączone **uwierzytelnianie dwuskładnikowe (2FA)**
3. Utwórz nowe hasło dla aplikacji (np. `Netflix Bot`)
4. Skopiuj wygenerowane hasło `xxxx xxxx xxxx xxxx` i wklej do `.env`

### 3. Bot na Discordzie

1. W [Developer Portal](https://discord.com/developers/applications) utwórz nową aplikację
2. W sekcji **Bot** włącz **Message Content Intent** i skopiuj token
3. W sekcji **OAuth2 → URL Generator** dodaj scope `bot` oraz uprawnienia `Send Messages` + `Embed Links`
4. Otwórz wygenerowany URL, aby dodać bota na serwer

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

| Komenda                  | Opis                                                                          |
| ------------------------ | ----------------------------------------------------------------------------- |
| `/kod-tymczasowy`        | Pobierz najnowszy link do kodu weryfikacyjnego (cooldown: 10s na użytkownika) |
| `/kod-logowanie`         | Pobierz 4-cyfrowy kod logowania z e-maila Netflixa                            |
| `/zmien-gospodarstwo`    | Zmienia gospodarstwo domowe (często spotykane przy logowaniu na TV/Konsoli)   |
| `/ping`                  | Sprawdza, czy bot jest online                                                 |
| `/pomoc`                 | Lista wszystkich komend                                                       |

---

## Jak to działa?

Bot przeszukuje skrzynkę Gmail (ostatnie 24h) pod kątem e-maili Netflixa:

- **Kod tymczasowy** (`/kod-tymczasowy`) — wyszukuje e-maile z tematem zgodnym z `EMAIL_SUBJECT_CODE`, wyciąga link weryfikacyjny z treści i publikuje go na Discordzie z odliczaniem do wygaśnięcia.
- **Kod logowania** (`/kod-logowanie`) — wyszukuje e-maile z tematem zgodnym z `EMAIL_SUBJECT_LOGIN_CODE`, wyciąga 4-cyfrowy kod z treści i zwraca go użytkownikowi.

### Gdzie publikować kod?

Ustaw `POST_DESTINATION` w `.env`:

- **`interaction`** (domyślnie) — kod trafia na kanał, gdzie użytkownik wpisał komendę
- **`channel`** — kod trafia na stały kanał określony w `DISCORD_CHANNEL_ID`. Jeśli `DISCORD_CHANNEL_ID` nie jest ustawione, kod trafia na pierwszy dostępny kanał.
