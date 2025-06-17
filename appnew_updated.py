import os
import streamlit as st
from dotenv import load_dotenv
import google.generativeai as genai
import pandas as pd
from io import BytesIO
import io
import csv
from fpdf import FPDF

# --- Load environment variables ---
load_dotenv()
VALID_USERNAME = "Shounak"
VALID_PASSWORD = "CG1234"
GOOGLE_API_KEY = "AIzaSyDzbx48T6HYPTmJm-LvIin-9BrVZ_6z6-s"

# --- Streamlit Config ---
st.set_page_config(page_title="GenAI Test Case Generator", layout="centered")
st.title("🧪 Guidewire PolicyCenter – GenAI Test Case Generator")

# --- Gemini Model Config ---
genai.configure(api_key=GOOGLE_API_KEY)
model = genai.GenerativeModel("gemini-2.0-flash-exp")

# --- PDF Generator ---
def generate_pdf_from_text(text: str) -> BytesIO:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    for line in text.splitlines():
        safe_line = line.encode("latin-1", errors="replace").decode("latin-1")
        pdf.multi_cell(0, 10, safe_line)
    buffer = BytesIO()
    pdf_output = pdf.output(dest="S").encode("latin-1", errors="replace")
    buffer.write(pdf_output)
    buffer.seek(0)
    return buffer

# --- Session State Init ---
if "brd_text" not in st.session_state:
    st.session_state.brd_text = ""

# --- Use Case Upload ---
st.subheader("📥 Upload or Paste Use Case")
usecase_file = st.file_uploader("Upload Use Case (.txt)", type=["txt"])
usecase_text = st.text_area("Or paste use case directly")

final_usecase = ""
if usecase_file:
    final_usecase = usecase_file.getvalue().decode("utf-8")
elif usecase_text.strip():
    final_usecase = usecase_text.strip()

# --- Manual BRD Generation ---
if final_usecase and st.button("📝 Generate BRD Manually"):
    with st.spinner("Generating BRD from use case..."):
        brd_prompt = f"Create a detailed Business Requirements Document (BRD) based on the following Guidewire PolicyCenter use case:\n\n{final_usecase}"
        response = model.generate_content(brd_prompt)
        st.session_state.brd_text = (
            response.candidates[0].content.parts[0].text.strip()
            if response and response.candidates and response.candidates[0].content.parts
            else ""
        )
# --- Download BRD (Optional) ---
if st.session_state.brd_text:
    st.download_button("⬇️ Download BRD (TXT)", data=st.session_state.brd_text,
                       file_name="generated_brd.txt", mime="text/plain")
    st.download_button("⬇️ Download BRD (PDF)", data=generate_pdf_from_text(st.session_state.brd_text),
                       file_name="generated_brd.pdf", mime="application/pdf")
# --- Template Upload ---
st.subheader("📋 Upload Sample Test Case Template")
template_file = st.file_uploader("Upload Template (.csv or .xlsx)", type=["csv", "xlsx"])
template_columns = []
if template_file:
    df_template = pd.read_csv(template_file) if template_file.name.endswith(".csv") else pd.read_excel(template_file)
    template_columns = list(df_template.columns)

# --- Generate Test Cases ---
if st.button("🚀 Generate Test Cases"):
    if not st.session_state.brd_text:
        st.warning("Please generate the BRD manually first.")
    elif not template_columns:
        st.warning("Please upload a valid test case template.")
    else:
        prompt_test_cases = f"""
You are a QA test case generator for Guidewire PolicyCenter. Based on the BRD below, do the following:

1. Automatically detect the transaction type (e.g., New Business, Policy Change, etc.).
2. Generate 5 detailed test cases.
3. Each test case must include:
   - Test Case Number (1, 2, 3...)
   - A descriptive Title
   - Preconditions
   - Detailed, numbered Steps
   - Expected Results
   - Module (e.g., Submission, Policy Change)
   - Status = Draft
   - Test Data (e.g., customer info, product, vehicle)

Output strict CSV format (comma-separated). Wrap all fields in double quotes, even multiline ones.
Do NOT include markdown or ``` formatting.

Use the exact headers below:
"Test Case Number","Title","Preconditions","Steps","Expected Results","Module","Status","Test Data"

BRD:
{st.session_state.brd_text}
        """

        with st.spinner("Generating Test Cases..."):
            response = model.generate_content(prompt_test_cases)
            output_text = (
                response.candidates[0].content.parts[0].text.strip()
                if response and response.candidates and response.candidates[0].content.parts
                else ""
            )

        # --- Clean and Parse Output ---
        cleaned = output_text.strip().strip("`").replace("```csv", "").replace("```", "")
        try:
            df_result = pd.read_csv(io.StringIO(cleaned), quoting=csv.QUOTE_ALL)
            expected_cols = [
                "Test Case Number", "Title", "Preconditions", "Steps",
                "Expected Results", "Module", "Status", "Test Data"
            ]
            for col in expected_cols:
                if col not in df_result.columns:
                    df_result[col] = ""
            df_result = df_result[expected_cols]
        except Exception as e:
            st.warning(f"Error parsing CSV: {e}")
            df_result = pd.DataFrame({"Output": [output_text]})

        # --- Show and Download ---
        st.subheader("✅ Generated Test Cases")
        st.dataframe(df_result, use_container_width=True, hide_index=True)

        excel_buffer = BytesIO()
        with pd.ExcelWriter(excel_buffer, engine='xlsxwriter') as writer:
            df_result.to_excel(writer, index=False, sheet_name="TestCases")
        excel_buffer.seek(0)

        st.download_button("⬇️ Download Excel", data=excel_buffer,
                           file_name="test_cases.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        st.download_button("⬇️ Download CSV", data=df_result.to_csv(index=False).encode("utf-8"),
                           file_name="test_cases.csv", mime="text/csv")


