import os
import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from lead_intelligence.discovery import classify_source, discover_from_website, google_maps_query
from lead_intelligence.commands import apply_command, parse_command
from lead_intelligence.extraction import extract_website_contacts
from lead_intelligence.pipeline import Columns, process_rows
from lead_intelligence.places import GooglePlaces
from lead_intelligence.verification import verify_rows_with_places

load_dotenv()
st.set_page_config(page_title="Lead Intelligence", page_icon="🔎", layout="wide")


def download(records, filename, key):
    if records:
        frame = pd.DataFrame(records)
        edited = st.data_editor(frame, use_container_width=True, num_rows="dynamic", key=f"editor_{key}")
        st.download_button("Download CSV", edited.to_csv(index=False).encode("utf-8-sig"), filename, "text/csv", key=f"download_{key}")


def places_tab():
    st.subheader("Google Maps lead discovery")
    st.caption("Uses Google Places API—not Google Maps webpage scraping. Search restaurants, hotels, salons, or any category/location.")
    query = st.text_input("Business search", placeholder="Boutique hotels in St. Moritz, Switzerland")
    limit = st.slider("Maximum results", 1, 20, 10)
    if not os.getenv("GOOGLE_PLACES_API_KEY"):
        st.info("Add GOOGLE_PLACES_API_KEY to .env to enable this tab. The rest works without it.")
    if st.button("Find businesses", type="primary", key="places_search"):
        if not query.strip():
            st.warning("Enter a business category and location.")
            return
        try:
            records = GooglePlaces().text_search(query, limit)
            st.success(f"Found {len(records)} businesses.")
            download(records, "google_places_leads.csv", "places")
        except Exception as error:
            st.error(f"Search failed: {error}")


def command_tab():
    st.subheader("Lead operations chat")
    st.caption("Run explainable filtering commands over an uploaded CSV. The local command parser works without an AI key.")
    uploaded = st.file_uploader("Upload leads for a command", type="csv", key="command_upload")
    prompt = st.text_input(
        "What should happen?",
        placeholder="Remove any hotel that is already managed by a company",
        key="lead_command",
    )
    if not uploaded or not prompt:
        st.info("Example: remove any hotel that is already under a management company.")
        return
    try:
        data = pd.read_csv(uploaded).fillna("")
    except Exception as error:
        st.error(f"Could not read CSV: {error}")
        return
    command = parse_command(prompt)
    st.write(f"Interpreted operation: `{command.action}`" + (f" for `{command.category}` records." if command.category else "."))
    if command.action == "unknown":
        st.warning("I could not map that prompt to a supported safe operation yet. Try remove, exclude, keep, or include with a category.")
        return
    if st.button("Run command", type="primary", key="run_lead_command"):
        kept, excluded = apply_command(data.to_dict("records"), command)
        st.session_state["command_kept"] = kept
        st.session_state["command_excluded"] = excluded
    if "command_kept" in st.session_state:
        st.success(f"Kept {len(st.session_state['command_kept'])} rows and excluded {len(st.session_state['command_excluded'])} rows.")
        download(st.session_state["command_kept"], "filtered_leads.csv", "command_kept")
        if st.session_state["command_excluded"]:
            download(st.session_state["command_excluded"], "excluded_leads.csv", "command_excluded")


def lead_generator_tab():
    st.subheader("Lead generation and Places verification")
    st.caption("For each imported name and address, query Google Places, select the best candidate, score similarity, and export verified contacts separately.")
    if not os.getenv("GOOGLE_PLACES_API_KEY"):
        st.info("Add GOOGLE_PLACES_API_KEY to .env for independent Google Places verification. Website and CSV workflows remain available without it.")
    uploaded = st.file_uploader("Upload source leads", type="csv", key="generator_upload")
    if not uploaded:
        return
    data = pd.read_csv(uploaded).fillna("")
    if data.empty:
        st.warning("The CSV contains no data rows.")
        return
    choices = [""] + list(data.columns)
    def select(label, default="", key=None):
        return st.selectbox(label, choices, index=choices.index(default) if default in choices else 0, key=key)
    one, two = st.columns(2)
    with one:
        name = select("Business name *", "business_name", "generator_name")
        address = select("Business address *", "business_address", "generator_address")
    with two:
        city = select("City", "city", "generator_city")
        postal = select("Postal code", "postal_code", "generator_postal")
    enrich = st.checkbox("Crawl each matched official website for public email and phone", value=True)
    if st.button("Generate and verify leads", type="primary", key="generate_leads"):
        if not name or not address:
            st.error("Map both business name and address.")
            return
        progress = st.progress(0, text="Searching Google Places…")
        def update(current, total):
            progress.progress(current / total, text=f"Verifying {current} of {total} leads")
        try:
            results = verify_rows_with_places(data.to_dict("records"), name, address, city, postal, progress=update)
            if enrich:
                cache = {}
                for result in results:
                    website = result.get("places_website", "")
                    if website:
                        details = cache.get(website) or extract_website_contacts(website, max_pages=3)
                        cache[website] = details
                        result["verified_public_email"] = "; ".join(details.get("emails", []))
                        result["verified_public_phone"] = "; ".join(details.get("phones", [])) or result.get("places_phone", "")
                        result["verified_contact_source_urls"] = "; ".join(details.get("source_urls", []))
                    else:
                        result["verified_public_email"] = ""
                        result["verified_public_phone"] = result.get("places_phone", "")
                        result["verified_contact_source_urls"] = result.get("places_source_url", "")
            st.session_state["generated_leads"] = results
        except Exception as error:
            st.error(f"Lead generation failed: {error}")
        progress.empty()
    if "generated_leads" in st.session_state:
        generated = pd.DataFrame(st.session_state["generated_leads"])
        st.dataframe(generated, use_container_width=True)
        verified = generated[generated["places_verification_status"].isin(["Verified", "Probable Match"])]
        contacts = verified[(verified["verified_public_email"].astype(str).str.strip() != "") | (verified["verified_public_phone"].astype(str).str.strip() != "")]
        st.success(f"Generated {len(generated)} matches and {len(contacts)} verified contact leads.")
        st.download_button("Download all verified matches", generated.to_csv(index=False).encode("utf-8-sig"), "places_verified_leads.csv", "text/csv", key="download_generated")
        st.download_button("Download verified contacts only", contacts.to_csv(index=False).encode("utf-8-sig"), "verified_lead_contacts.csv", "text/csv", key="download_contacts")


def website_tab():
    st.subheader("Discover businesses from a webpage")
    st.caption("Paste a public directory, listing, or category page. The scraper checks structured data first, then repeated listing cards.")
    url = st.text_input("Public webpage URL", placeholder="https://example.com/restaurants/zurich")
    browser_mode = st.checkbox("Use browser mode for JavaScript pages and ordinary consent popups", help="Requires Playwright + Chromium; it does not bypass logins, CAPTCHAs, paywalls, or bot protection.")
    if st.button("Analyze webpage", type="primary", key="website_discovery"):
        if not url.strip():
            st.warning("Paste a public URL.")
            return
        source_type = classify_source(url)
        if source_type == "google_maps":
            st.warning("This is a Google Maps URL. Use the Google Maps lead discovery tab; suggested query:")
            st.code(google_maps_query(url) or "No readable query found—enter a category and location manually.")
            return
        if source_type == "search_engine":
            st.warning("Search-engine result pages are not scraped. Use Google Places or paste the destination directory page.")
            return
        with st.spinner("Analyzing public page structure…"):
            result = discover_from_website(url, browser_mode)
        if result.message:
            st.info(result.message)
        if result.records:
            st.success(f"Discovered {len(result.records)} possible businesses. Review before enrichment.")
            download(result.records, "website_discovered_leads.csv", "website")


def csv_tab():
    st.subheader("Verify and enrich an existing CSV")
    uploaded = st.file_uploader("Upload a lead CSV", type="csv")
    if not uploaded:
        st.info("Use `property_booking_non_hotels.csv`, a Google Places export, or another compatible CSV.")
        return
    try:
        data = pd.read_csv(uploaded).fillna("")
    except Exception as error:
        st.error(f"Could not read CSV: {error}")
        return
    if data.empty:
        st.warning("The CSV contains no data rows.")
        return
    st.dataframe(data.head(10), use_container_width=True)
    choices = [""] + list(data.columns)
    def select(label, default="", key=None):
        return st.selectbox(label, choices, index=choices.index(default) if default in choices else 0, key=key)
    st.markdown("#### Source lead columns")
    one, two = st.columns(2)
    with one:
        name, address, city = select("Business name *", "property_name"), select("Business address *", "full_address"), select("City", "city")
    with two:
        postal, website = select("Postal code", "postal_code"), select("Official website", "website")
        crawl = st.checkbox("Crawl mapped public websites", value=False, disabled=not website)
    st.markdown("#### Independent candidate evidence")
    st.caption("Map fields from Google Places or another approved source. Empty fields remain unverified—not matched to themselves.")
    one, two = st.columns(2)
    with one:
        candidate_name = select("Candidate business name", "gmaps_name", "candidate_name")
        candidate_address = select("Candidate address", "gmaps_address", "candidate_address")
    with two:
        candidate_city = select("Candidate city", "", "candidate_city")
        candidate_postal = select("Candidate postal code", "", "candidate_postal")
        candidate_source_url = select("Independent candidate source URL", "source_url", "candidate_source_url")
    st.caption("A candidate source URL is required for verification. This prevents a lead from verifying itself.")
    ai_review = st.checkbox("Use AI review only for uncertain candidate matches", value=False, disabled=not bool(os.getenv("OPENAI_API_KEY")))
    if st.button("Process leads", type="primary", key="csv_process"):
        if not name or not address:
            st.error("Map both business name and address.")
            return
        progress = st.progress(0, text="Preparing records…")
        def update(current, total):
            progress.progress(current / total, text=f"Processing {current} of {total} leads")
        results = process_rows(
            data.to_dict("records"),
            Columns(name, address, city, postal, website, candidate_name, candidate_address, candidate_city, candidate_postal, candidate_source_url),
            crawl_websites=crawl,
            ai_review=ai_review,
            progress=update,
        )
        progress.empty()
        output = pd.DataFrame(results)
        st.success(f"Processed {len(output)} leads.")
        counts = output["final_verification_status"].value_counts()
        for label, column in zip(["Verified", "Probable Match", "Needs Manual Review", "Rejected", "No Information Found"], st.columns(5)):
            column.metric(label, int(counts.get(label, 0)))
        st.session_state["processed_leads"] = output
    if "processed_leads" in st.session_state:
        download(st.session_state["processed_leads"].to_dict("records"), "verified_leads.csv", "verified")


def main():
    st.title("AI-Assisted Lead Intelligence")
    st.caption("Discover → review → enrich → verify. AI is an evidence-bound assistant, not an autonomous scraper.")
    places, website, csv, commands, generator = st.tabs(["Google Maps / Places", "Paste Website URL", "Upload CSV", "Lead Chat", "Lead Generator"])
    with places:
        places_tab()
    with website:
        website_tab()
    with csv:
        csv_tab()
    with commands:
        command_tab()
    with generator:
        lead_generator_tab()


if __name__ == "__main__":
    main()
