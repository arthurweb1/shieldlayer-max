# ShieldLayer Max — Chrome Extension

Manifest V3 Chrome Extension that intercepts text inputs on AI platforms
and masks PII before the data reaches the model.

## Supported platforms
- ChatGPT (chatgpt.com / chat.openai.com)
- Claude (claude.ai)
- Gemini (gemini.google.com)
- Microsoft Copilot (copilot.microsoft.com)

## Installation (Development)
1. Open Chrome → `chrome://extensions`
2. Enable **Developer mode** (top right)
3. Click **Load unpacked**
4. Select this folder

## How it works
1. Content script monitors all `<textarea>` and `contenteditable` inputs
2. On Enter key: scans for PII patterns (EMAIL, IBAN, PHONE, PERSON, CREDIT_CARD)
3. If PII found: scanline animation → text masked to `[PERSON_1]` etc. → submission continues
4. License key validates via `POST /api/license/validate`
5. One license key = N seats (configured at purchase)

## License Activation
1. Click the extension icon
2. Enter your license key (format: `SL-XXXX-XXXX-XXXX-XXXX`)
3. Click Activate — validates against shieldlayer.ai API

## Building for distribution
```bash
# Zip for Chrome Web Store submission
zip -r shieldlayer-max-extension.zip . --exclude "*.git*" --exclude "README.md"
```
