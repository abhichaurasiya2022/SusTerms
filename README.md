# 🛡️ SusTerms – Contract Risk Analyzer (WIP)

**SusTerms** is a Flask web app that helps users understand the legal risks in contracts, Terms of Service, and EULAs by:
- Summarizing text with AI (Gemini)
- Highlighting risky clauses using legal keyword analysis
- Allowing users to upload files or paste content
- Supporting edit/update/delete of previous analyses

OCR support is currently **work-in-progress**.

---

## ✨ Features

- 📄 Paste or upload contract content
- 🧠 Summarization via Google Gemini API
- ⚠️ Highlight of potentially risky clauses
- 💾 Save, edit, delete analysis entries
- 🧑‍💼 User login and authentication
- 📦 MongoDB-backed data storage
- 🛠️ OCR support (coming soon)

---

## 🧪 Tech Stack

- **Backend:** Flask (Python)
- **Frontend:** HTML + Jinja + MaterializeCSS
- **OCR:** Tesseract (via `pytesseract`) – *in progress*
- **AI Summarization:** Google Gemini API
- **Database:** MongoDB Atlas via `pymongo`
- **Auth:** Flask sessions + bcrypt

---

## 🚀 Getting Started

### 1. Clone the repo

```bash
git clone https://github.com/abhichaurasiya2022/susterms.git
cd susterms
