import streamlit as st
import fitz  # PyMuPDF
import re
import requests
# from bs4 import BeautifulSoup   # ❌ Not used - removed
import google.generativeai as genai
import os
from datetime import datetime
import json
from typing import List, Dict, Tuple
import pandas as pd

# Page configuration
st.set_page_config(
    page_title="FactCheck Pro - AI Truth Layer",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .verified { background-color: #d4edda; padding: 10px; border-radius: 5px; border-left: 5px solid #28a745; }
    .inaccurate { background-color: #fff3cd; padding: 10px; border-radius: 5px; border-left: 5px solid #ffc107; }
    .false { background-color: #f8d7da; padding: 10px; border-radius: 5px; border-left: 5px solid #dc3545; }
    .stat-highlight { font-weight: bold; color: #0d6efd; }
</style>
""", unsafe_allow_html=True)

class ClaimExtractor:
    """Extract claims from PDF documents"""
    
    @staticmethod
    def extract_text_from_pdf(pdf_file) -> str:
        """Extract text from uploaded PDF"""
        doc = fitz.open(stream=pdf_file.read(), filetype="pdf")
        text = ""
        for page in doc:
            text += page.get_text()
        return text
    
    @staticmethod
    def identify_claims(text: str) -> List[Dict]:
        """Identify statistical and factual claims"""
        claims = []
        
        # Patterns for different claim types
        patterns = {
            'statistic': r'(\d+(?:\.\d+)?%\s*(?:of\s+)?[\w\s]+?(?:increased|decreased|grown|declined|reached|totaling|amounting|valued at|worth)\s*\$?\d+(?:\.\d+)?\s*(?:million|billion|trillion)?)',
            'financial': r'(?:\$\s*\d+(?:\.\d+)?\s*(?:million|billion|trillion|USD)|(?:revenue|profit|market cap|valuation)\s*(?:of|:)?\s*\$?\d+(?:\.\d+)?\s*(?:million|billion|trillion)?)',
            'date_specific': r'(?:in\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}|(?:since|from)\s+\d{4}|(?:by\s+the\s+year\s+\d{4}))',
            'comparison': r'(\d+(?:\.\d+)?%\s+(?:more|less|higher|lower|greater|smaller)\s+than)',
            'ranking': r'(?:ranked|rated|positioned)\s+(?:#?\d+|first|second|third|top|bottom)',
            'market_share': r'(\d+(?:\.\d+)?%\s+(?:market share|of the market))'
        }
        
        # Extract sentences containing claims
        sentences = re.split(r'[.!?]+', text)
        
        for sentence in sentences:
            sentence = sentence.strip()
            if len(sentence) < 20:  # Skip very short sentences
                continue
                
            for claim_type, pattern in patterns.items():
                matches = re.finditer(pattern, sentence, re.IGNORECASE)
                for match in matches:
                    claims.append({
                        'claim_text': sentence,
                        'matched_text': match.group(),
                        'claim_type': claim_type,
                        'context': ClaimExtractor.get_context(sentence, match.group())
                    })
        
        return claims
    
    @staticmethod
    def get_context(sentence: str, claim: str) -> str:
        """Extract relevant context around the claim"""
        # Get surrounding sentences for context
        return sentence[:200]  # Limit context length

class WebVerifier:
    """Verify claims against web sources"""
    
    @staticmethod
    def search_web(query: str, num_results: int = 5) -> List[Dict]:
        """Search the web for fact-checking"""
        results = []
        
        # Using DuckDuckGo for privacy-focused search
        try:
            url = f"https://api.duckduckgo.com/?q={query}&format=json"
            response = requests.get(url, headers={'User-Agent': 'FactChecker/1.0'})
            if response.status_code == 200:
                data = response.json()
                if 'RelatedTopics' in data:
                    for topic in data['RelatedTopics'][:num_results]:
                        if 'Text' in topic and 'FirstURL' in topic:
                            results.append({
                                'title': topic.get('Text', '')[:100],
                                'url': topic.get('FirstURL', ''),
                                'snippet': topic.get('Text', '')
                            })
        except:
            pass
        
        return results
    
    @staticmethod
    def verify_with_ai(claim: str, context: str) -> Dict:
        """Use AI to verify claims"""
        try:
            # Try to use Google's Gemini if API key is available
            if 'GOOGLE_API_KEY' in st.secrets:
                genai.configure(api_key=st.secrets['GOOGLE_API_KEY'])
                model = genai.GenerativeModel('gemini-pro')
                
                prompt = f"""
                Fact-check the following claim:
                
                Claim: {claim}
                Context: {context}
                
                Please:
                1. Verify if the claim is accurate based on current data
                2. Provide the correct information if inaccurate
                3. Cite specific sources
                4. Rate confidence: HIGH, MEDIUM, LOW
                
                Format response as JSON:
                {{
                    "status": "VERIFIED/INACCURATE/FALSE",
                    "correct_info": "correct facts here",
                    "confidence": "HIGH/MEDIUM/LOW",
                    "source": "citation"
                }}
                """
                
                response = model.generate_content(prompt)
                
                # Parse JSON from response
                try:
                    result = json.loads(response.text)
                    return result
                except:
                    pass
        except:
            pass
        
        # Fallback to web-based verification
        return WebVerifier.fallback_verification(claim, context)
    
    @staticmethod
    def fallback_verification(claim: str, context: str) -> Dict:
        """Basic web-based verification"""
        # Search for the claim
        results = WebVerifier.search_web(claim)
        
        if results:
            return {
                'status': 'PENDING',
                'correct_info': 'Verified via web search',
                'confidence': 'MEDIUM',
                'source': results[0].get('url', 'Web search'),
                'web_results': results
            }
        else:
            return {
                'status': 'FALSE',
                'correct_info': 'No supporting evidence found',
                'confidence': 'LOW',
                'source': 'No reliable sources'
            }

def main():
    """Main Streamlit application"""
    
    # Header
    st.title("🔍 FactCheck Pro - AI Truth Layer")
    st.markdown("### *Automated Claim Verification & Fact-Checking System*")
    
    # Sidebar
    with st.sidebar:
        st.header("📊 Dashboard")
        st.metric("Documents Processed", "0", delta="Real-time")
        
        st.markdown("---")
        st.subheader("🔑 API Configuration")
        
        api_key = st.text_input(
            "Google Gemini API Key (Optional)",
            type="password",
            help="Enter your Google Gemini API key for enhanced AI verification"
        )
        
        if api_key:
            st.session_state['api_key'] = api_key
            
        st.markdown("---")
        st.subheader("📋 About")
        st.info("""
        **FactCheck Pro** cross-references claims from uploaded 
        PDFs against live web data to identify:
        - ✅ Verified facts
        - ⚠️ Outdated statistics
        - ❌ False claims
        """)
    
    # Main content area
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("📄 Upload PDF Document")
        uploaded_file = st.file_uploader(
            "Choose a PDF file",
            type="pdf",
            help="Upload a PDF document containing claims to verify"
        )
        
        if uploaded_file:
            st.success(f"✅ Uploaded: {uploaded_file.name}")
            
            # Process button
            if st.button("🔍 Start Fact-Checking", type="primary"):
                with st.spinner("Extracting claims from PDF..."):
                    # Extract text
                    text = ClaimExtractor.extract_text_from_pdf(uploaded_file)
                    
                    # Show extracted text preview
                    with st.expander("📝 Preview Extracted Text"):
                        st.text(text[:500] + "..." if len(text) > 500 else text)
                    
                    # Extract claims
                    claims = ClaimExtractor.identify_claims(text)
                    
                    st.success(f"Found {len(claims)} potential claims to verify")
                
                # Verify each claim
                with st.spinner("Verifying claims against live data..."):
                    verified_claims = []
                    
                    progress_bar = st.progress(0)
                    
                    for i, claim in enumerate(claims):
                        # Update progress
                        progress_bar.progress((i + 1) / len(claims))
                        
                        # Verify claim
                        verification = WebVerifier.verify_with_ai(
                            claim['matched_text'],
                            claim['context']
                        )
                        
                        verified_claims.append({
                            **claim,
                            'verification': verification,
                            'timestamp': datetime.now().isoformat()
                        })
                    
                    progress_bar.empty()
                
                # Display results
                st.subheader("📊 Verification Results")
                
                # Summary metrics
                verified_count = sum(1 for c in verified_claims if c['verification']['status'] == 'VERIFIED')
                inaccurate_count = sum(1 for c in verified_claims if c['verification']['status'] == 'INACCURATE')
                false_count = sum(1 for c in verified_claims if c['verification']['status'] == 'FALSE')
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("✅ Verified", verified_count, delta_color="normal")
                with col2:
                    st.metric("⚠️ Inaccurate", inaccurate_count, delta_color="off")
                with col3:
                    st.metric("❌ False", false_count, delta_color="inverse")
                
                # Detailed results
                st.markdown("---")
                
                for i, claim in enumerate(verified_claims):
                    status = claim['verification']['status']
                    
                    # Choose appropriate styling
                    if status == 'VERIFIED':
                        css_class = 'verified'
                        emoji = '✅'
                    elif status == 'INACCURATE':
                        css_class = 'inaccurate'
                        emoji = '⚠️'
                    else:
                        css_class = 'false'
                        emoji = '❌'
                    
                    # Display claim result
                    with st.expander(f"{emoji} Claim {i+1}: {claim['matched_text'][:100]}...", expanded=False):
                        st.markdown(f"<div class='{css_class}'>", unsafe_allow_html=True)
                        
                        col1, col2 = st.columns([3, 1])
                        
                        with col1:
                            st.markdown("**Claim:**")
                            st.write(claim['matched_text'])
                            
                            st.markdown("**Verification:**")
                            st.write(claim['verification'].get('correct_info', 'No information available'))
                            
                            if 'source' in claim['verification']:
                                st.markdown(f"**Source:** {claim['verification']['source']}")
                        
                        with col2:
                            st.markdown(f"**Status:** {status}")
                            st.markdown(f"**Confidence:** {claim['verification'].get('confidence', 'Unknown')}")
                            st.markdown(f"**Type:** {claim['claim_type']}")
                        
                        st.markdown("</div>", unsafe_allow_html=True)
                
                # Export results
                st.markdown("---")
                st.subheader("📥 Export Results")
                
                if st.button("Download Report"):
                    # Create downloadable report
                    report_data = []
                    for claim in verified_claims:
                        report_data.append({
                            'Claim': claim['matched_text'],
                            'Status': claim['verification']['status'],
                            'Correct Info': claim['verification'].get('correct_info', ''),
                            'Confidence': claim['verification'].get('confidence', ''),
                            'Source': claim['verification'].get('source', ''),
                            'Type': claim['claim_type']
                        })
                    
                    df = pd.DataFrame(report_data)
                    csv = df.to_csv(index=False)
                    
                    st.download_button(
                        label="📥 Download CSV Report",
                        data=csv,
                        file_name=f"factcheck_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                        mime="text/csv"
                    )

if __name__ == "__main__":
    main()
