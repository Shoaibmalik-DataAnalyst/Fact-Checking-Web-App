# 🔍 FactCheck Pro - AI Truth Layer

An automated fact-checking web application that verifies claims from PDF documents against live web data.

## 🌟 Features

- **PDF Text Extraction**: Extracts text and identifies claims from uploaded PDFs
- **AI-Powered Verification**: Uses Google Gemini API for intelligent fact-checking
- **Web Cross-Referencing**: Validates claims against current web data
- **Visual Reporting**: Color-coded results with confidence levels
- **Export Functionality**: Download verification reports as CSV

## 🚀 Quick Deploy

### Deploy to Streamlit Cloud (Free)

1. Fork this repository
2. Go to [Streamlit Cloud](https://streamlit.io/cloud)
3. Click "New app"
4. Select your forked repository
5. Deploy!

### Local Development

```bash
# Clone the repository
git clone https://github.com/yourusername/factcheck-pro.git
cd factcheck-pro

# Install dependencies
pip install -r requirements.txt

# Run the app
streamlit run app.py
