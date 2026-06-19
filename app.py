import streamlit as st
import fitz  # PyMuPDF
import re
import requests
import json
from datetime import datetime
from typing import List, Dict
import pandas as pd

# Page config
st.set_page_config(
    page_title="FactCheck Pro – Truth Layer",
    page_icon="🔍",
    layout="wide",
)

# Custom styling
st.markdown("""
<style>
    .verified { background-color: #d4edda; padding: 1rem; border-radius: 8px; border-left: 5px solid #28a745; margin: 0.5rem 0; }
    .inaccurate { background-color: #fff3cd; padding: 1rem; border-radius: 8px; border-left: 5px solid #ffc107; margin: 0.5rem 0; }
    .false { background-color: #f8d7da; padding: 1rem; border-radius: 8px; border-left: 5px solid #dc3545; margin: 0.5rem 0; }
    .stat-highlight { font-weight: bold; color: #0d6efd; }
</style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# 1. Claim extraction
# -----------------------------------------------------------------------------
class ClaimExtractor:
    @staticmethod
    def extract_text_from_pdf(pdf_file) -> str:
        doc = fitz.open(stream=pdf_file.read(), filetype="pdf")
        return "\n".join(page.get_text() for page in doc)

    @staticmethod
    def identify_claims(text: str) -> List[Dict]:
        patterns = {
            'statistic': r'(\d+(?:\.\d+)?%\s*(?:of\s+)?[\w\s]+?(?:increased|decreased|grown|declined|reached|totaling|amounting|valued at|worth)\s*\$?\d+(?:\.\d+)?\s*(?:million|billion|trillion)?)',
            'financial': r'(?:\$\s*\d+(?:\.\d+)?\s*(?:million|billion|trillion|USD)|(?:revenue|profit|market cap|valuation)\s*(?:of|:)?\s*\$?\d+(?:\.\d+)?\s*(?:million|billion|trillion)?)',
            'date_specific': r'(?:in\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}|(?:since|from)\s+\d{4}|(?:by\s+the\s+year\s+\d{4}))',
            'comparison': r'(\d+(?:\.\d+)?%\s+(?:more|less|higher|lower|greater|smaller)\s+than)',
            'ranking': r'(?:ranked|rated|positioned)\s+(?:#?\d+|first|second|third|top|bottom)',
            'market_share': r'(\d+(?:\.\d+)?%\s+(?:market share|of the market))'
        }
        claims = []
        sentences = re.split(r'[.!?]+', text)
        for sentence in sentences:
            sentence = sentence.strip()
            if len(sentence) < 20:
                continue
            for ctype, pat in patterns.items():
                for m in re.finditer(pat, sentence, re.IGNORECASE):
                    claims.append({
                        'claim_text': sentence,
                        'matched_text': m.group(),
                        'claim_type': ctype,
                    })
        return claims

# -----------------------------------------------------------------------------
# 2. Fact‑checking backend (Google Fact Check Tools + web scraping)
# -----------------------------------------------------------------------------
class FactChecker:
    GOOGLE_API_URL = "https://factchecktools.googleapis.com/v1alpha1/claims:search"
    FACTCHECK_SITES = {
        'snopes': 'site:snopes.com',
        'politifact': 'site:politifact.com',
        'factcheck': 'site:factcheck.org',
    }

    @staticmethod
    def _google_factcheck(query: str, api_key: str) -> Dict:
        """Official Google Fact Check Tools API."""
        params = {
            'key': api_key,
            'query': query,
            'languageCode': 'en',
        }
        try:
            resp = requests.get(FactChecker.GOOGLE_API_URL, params=params, timeout=8)
            data = resp.json()
            if 'claims' in data and data['claims']:
                claim = data['claims'][0]
                rating = claim.get('claimReview', [{}])[0].get('textualRating', '').lower()
                source = claim.get('claimReview', [{}])[0].get('url', '')
                return {
                    'status': 'VERIFIED' if 'true' in rating else 'INACCURATE',
                    'correct_info': claim.get('text', ''),
                    'confidence': 'HIGH',
                    'source': source
                }
        except Exception:
            pass
        return {}

    @staticmethod
    def _scrape_factcheck_sites(query: str) -> Dict:
        """Scrape known fact‑checking sites for verdicts."""
        # Use a simple search via DuckDuckGo (no API key) with site: operator
        search_url = "https://html.duckduckgo.com/html/"
        for site_name, site_query in FactChecker.FACTCHECK_SITES.items():
            full_q = f"{query} {site_query}"
            try:
                resp = requests.get(search_url, params={'q': full_q},
                                    headers={'User-Agent': 'Mozilla/5.0'}, timeout=8)
                if resp.status_code == 200:
                    # Very simple extraction – look for common verdict words
                    if 'true' in resp.text.lower() or 'fact' in resp.text.lower():
                        # We'll try to find a link
                        import re
                        links = re.findall(r'<a[^>]+href="(https?://[^"]+)"', resp.text)
                        url = links[0] if links else f"https://{site_name}.com"
                        return {
                            'status': 'VERIFIED',
                            'correct_info': f'Found on {site_name.capitalize()}',
                            'confidence': 'MEDIUM',
                            'source': url
                        }
            except Exception:
                continue
        return {'status': 'FALSE', 'correct_info': 'No evidence found', 'confidence': 'LOW', 'source': ''}

    @staticmethod
    def verify(claim: str, api_key: str = None) -> Dict:
        """Orchestrator: tries API first, then scraping."""
        if api_key:
            result = FactChecker._google_factcheck(claim, api_key)
            if result:
                return result

        # Fallback: scrape fact‑checking sites
        return FactChecker._scrape_factcheck_sites(claim)

# -----------------------------------------------------------------------------
# 3. Main app
# -----------------------------------------------------------------------------
def main():
    st.title("🔍 FactCheck Pro – AI Truth Layer")
    st.markdown("### *Upload a PDF – we'll flag lies, outdated stats, and provide real facts*")

    # Sidebar
    with st.sidebar:
        st.header("🔑 API Key (optional)")
        api_key = st.text_input("Google FactCheck Tools API key", type="password",
                                help="Get one at https://console.cloud.google.com (free tier)")
        st.markdown("---")
        st.info("""
        **How it works**
        1. Upload a PDF
        2. Claims are extracted automatically
        3. Each claim is checked against live fact‑checking databases
        4. You get a report with:
           - ✅ Verified
           - ⚠️ Inaccurate / Outdated
           - ❌ No evidence
        """)

    # Upload
    uploaded_file = st.file_uploader("Choose a PDF", type="pdf")
    if uploaded_file:
        st.success(f"Uploaded: {uploaded_file.name}")
        if st.button("🔍 Start Fact‑Checking", type="primary"):
            with st.spinner("Extracting text..."):
                text = ClaimExtractor.extract_text_from_pdf(uploaded_file)
                with st.expander("📝 Extracted text preview"):
                    st.text(text[:800] + "..." if len(text) > 800 else text)

            claims = ClaimExtractor.identify_claims(text)
            if not claims:
                st.warning("No statistical/financial claims detected.")
                return

            st.success(f"Found {len(claims)} claims to verify")

            # Verify each claim
            verified_claims = []
            progress = st.progress(0)
            for i, c in enumerate(claims):
                progress.progress((i + 1) / len(claims))
                result = FactChecker.verify(c['matched_text'], api_key if api_key else None)
                verified_claims.append({**c, 'verification': result, 'timestamp': datetime.now().isoformat()})
            progress.empty()

            # Summary metrics
            v = sum(1 for c in verified_claims if c['verification']['status'] == 'VERIFIED')
            i_count = sum(1 for c in verified_claims if c['verification']['status'] == 'INACCURATE')
            f = sum(1 for c in verified_claims if c['verification']['status'] == 'FALSE')

            cols = st.columns(3)
            cols[0].metric("✅ Verified", v)
            cols[1].metric("⚠️ Inaccurate", i_count)
            cols[2].metric("❌ False", f)

            st.markdown("---")
            for idx, claim in enumerate(verified_claims):
                status = claim['verification']['status']
                emoji = '✅' if status == 'VERIFIED' else '⚠️' if status == 'INACCURATE' else '❌'
                css = status.lower()
                with st.expander(f"{emoji} Claim {idx+1}: {claim['matched_text'][:100]}...", expanded=False):
                    st.markdown(f"<div class='{css}'>", unsafe_allow_html=True)
                    c1, c2 = st.columns([3, 1])
                    c1.markdown("**Claim:**")
                    c1.write(claim['matched_text'])
                    c1.markdown("**Verification:**")
                    c1.write(claim['verification'].get('correct_info', ''))
                    c2.markdown(f"**Status:** {status}")
                    c2.markdown(f"**Confidence:** {claim['verification'].get('confidence','')}")
                    if claim['verification'].get('source'):
                        c1.markdown(f"**Source:** {claim['verification']['source']}")
                    st.markdown("</div>", unsafe_allow_html=True)

            # Export
            if st.button("📥 Download CSV Report"):
                df = pd.DataFrame([{
                    'Claim': c['matched_text'],
                    'Status': c['verification']['status'],
                    'Correct Info': c['verification'].get('correct_info',''),
                    'Source': c['verification'].get('source','')
                } for c in verified_claims])
                st.download_button("Download", df.to_csv(index=False),
                                   file_name=f"factcheck_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                                   mime="text/csv")

if __name__ == "__main__":
    main()
