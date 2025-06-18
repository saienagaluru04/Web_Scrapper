import time
import pandas as pd
import streamlit as st
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup 
import traceback
import json

# Streamlit Page Config
st.set_page_config(page_title="Web Scraper", page_icon="🛠", layout="wide")

# Main Navigation
st.sidebar.title("Navigation 🔍")
page = st.sidebar.radio("Go to", ["Home", "Bus Scraper 🚌", "Train Scraper 🚆"])

#------Standaridization of Gov bus names-------
def standardize_Gov_bus_name(raw_titles):
    if "service number" in raw_titles.lower():
        return "Government Bus"
    return raw_titles

# ---- Standardization Functions ----
def standardize_bus_type(bus_type_raw):
    bt_lower = bus_type_raw.lower()
    if "normal" in bt_lower: # Specific rule from document
        return "Non-AC Seater"
    has_non_ac = "non-ac" in bt_lower or "a/c" in bt_lower or "a.c." in bt_lower
    has_seater = "seater" in bt_lower
    has_sleeper = "sleeper" in bt_lower
    if has_non_ac:
        if has_seater and has_sleeper: return "Non-AC Seater-Sleeper"
        elif has_sleeper: return "Non-AC Sleeper"
        elif has_seater: return "Non-AC Seater"  
    else: # AC Buses
        if has_seater and has_sleeper: return "AC Seater-Sleeper"
        elif has_sleeper: return "AC Sleeper"
        elif has_seater: return "AC Seater"
    # If no specific 6-category rule matched, return the original type as a fallback
    print(f"Bus type '{bus_type_raw}' did not match a standard category, returning as is.")
    return bus_type_raw

def standardize_train_name(train_name_raw):
    if not train_name_raw or train_name_raw == "N/A":
        return "N/A"
    name_lower = train_name_raw.lower()
    name_lower_trim = name_lower.replace(" ","")
    if "vande bharat" in name_lower_trim or "vandebharat" in name_lower_trim: return "VandeBharat"
    if "sf" in name_lower_trim and "spl" in name_lower_trim: return "Superfast Special"
    if "sf" in name_lower_trim and ("exp" in name_lower_trim or "ex" in name_lower_trim): return "Superfast Express"
    if "sf" in name_lower_trim: return "Superfast"
    if "spl" in name_lower_trim and ("exp" in name_lower_trim or "ex" in name_lower_trim): return "Special Express"
    if "spl" in name_lower_trim: return "Special"
    if "exp" in name_lower_trim or "ex" in name_lower_trim: return "Express"
    return train_name_raw

# ---- Setup Selenium Web Driver ----
def setup_driver():
    service = Service(ChromeDriverManager().install())
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
    options.page_load_strategy = 'normal'
    options.add_experimental_option("prefs", {"profile.managed_default_content_settings.images": 2})
    return webdriver.Chrome(service=service, options=options)

# Updated extract_text for BeautifulSoup elements
def extract_bs_text(elements):
    extracted_text = []
    for elem in elements:
        temp = elem.get_text(strip=True) # Use get_text() for BeautifulSoup
        if temp:
            extracted_text.append(temp)
    return extracted_text

# ---- Expand Government Bus Dropdowns (Selenium interaction) ----
def expand_government_buses(driver):
    # This function remains the same as it requires Selenium interaction
    st.write("Attempting to expand government bus sections (if needed)...")
    print("Attempting to expand government bus sections (if needed)...")
    try:
        wait = WebDriverWait(driver, 10) 
        dropdown_selector = 'a.btn.dark.filled.primary.sm.rounded-sm.inactive.button'
        
        dropdown_buttons = wait.until(EC.presence_of_all_elements_located((
            By.CSS_SELECTOR, dropdown_selector
        )))

        if not dropdown_buttons:
            print("No government bus dropdown buttons found with the primary selector.")
        else:
            print(f"Found {len(dropdown_buttons)} potential government dropdown button(s).")
            for i, button in enumerate(dropdown_buttons):
                try:
                    button_text = button.text.lower() if button.text else ""
                    if button.is_displayed() and button.is_enabled() and "hide" not in button_text:
                        print(f"Attempting to click dropdown #{i + 1} (text: '{button.text}')")
                        driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center', inline: 'nearest'});", button)
                        time.sleep(0.5)
                        button.click()
                        print(f"Clicked dropdown #{i + 1}.")
                        st.write(f"Clicked dropdown #{i + 1} (text was: '{button.text}').")
                        time.sleep(2.5) # INCREASED sleep after click for content to fully render
                    elif "hide" in button_text:
                        print(f"Skipped clicking dropdown #{i + 1} (text: '{button.text}')")
                    # else:
                        # print(f"Skipped clicking dropdown #{i + 1} (text: '{button.text}') - not displayed/enabled.")
                except Exception as click_error:
                    print(f"Failed to interact with or click dropdown #{i + 1}: {click_error}")
                    st.warning(f"Error with dropdown button #{i+1}: {click_error}")
    except TimeoutException:
        print(f"Timed out waiting for government bus dropdown buttons.")
    except Exception as e:
        print(f"Error in expand_government_buses: {e}")

# ---- Bus Scraper (Using BeautifulSoup) ----
def scrape_buses_from_source(page_source_html, route_type):
    all_buses_data = []
    st.write("Parsing HTML with BeautifulSoup and extracting bus data...")
    print("Parsing HTML with BeautifulSoup and extracting bus data...")
    
    try:
        soup = BeautifulSoup(page_source_html, 'lxml') # Use lxml parser for speed

        # Using your original class names for finding elements with BeautifulSoup
        raw_titles_bs = extract_bs_text(soup.find_all(class_="title"))
        titles = [standardize_Gov_bus_name(rt) for rt in raw_titles_bs]
        
        raw_subtitles_bs = extract_bs_text(soup.find_all(class_="sub-title"))
        subtitles = [standardize_bus_type(st) for st in raw_subtitles_bs]
        
        departures = extract_bs_text(soup.find_all(class_="departure-time"))
        arrivals = extract_bs_text(soup.find_all(class_="arrival-time"))
        sources = extract_bs_text(soup.find_all(class_="source-name"))
        durations = extract_bs_text(soup.find_all(class_="travel-time"))
        destinations = extract_bs_text(soup.find_all(class_="destination-name"))
        
        # Fares extraction - CSS selector for 'span' with class 'fare'
        fares_raw_elements_bs = soup.select("span.fare") # soup.select is powerful for CSS selectors
        fares_raw_text = extract_bs_text(fares_raw_elements_bs)
    
        fares_processed = []
        for fare_text in fares_raw_text:
            fare_clean = fare_text.replace("₹", "").replace(",", "").strip()
            try:
                base_price = int(float(fare_clean))
                new_price = base_price + 300
                fares_processed.append(f"{base_price} - {new_price}")
            except ValueError:
                fares_processed.append(fare_text)

        counts_msg = (f"BS Extracted counts: Titles={len(titles)}, Subtitles={len(subtitles)}, "
                      f"Departures={len(departures)}, Arrivals={len(arrivals)}, Sources={len(sources)}, "
                      f"Durations={len(durations)}, Destinations={len(destinations)}, Fares={len(fares_processed)}")
        print(counts_msg)
        st.write(counts_msg)

        data_lists = [titles, subtitles, departures, arrivals, sources, durations, destinations, fares_processed]
        non_empty_lists = [lst for lst in data_lists if lst] 

        if not non_empty_lists:
            st.warning("All data fields returned empty from BeautifulSoup parsing.")
            print("Warning: All data fields returned empty from BeautifulSoup parsing.")
            return []

        min_len = min(len(lst) for lst in non_empty_lists)
        
        if min_len == 0 and any(len(lst) > 0 for lst in data_lists):
            st.warning("BS: Critical data list might be empty. Min_len is 0.")
            print("BS Warning: Min_len is 0, but some lists have data.")
            return []

        if min_len > 0:
            titles = titles[:min_len]
            subtitles = subtitles[:min_len]
            departures = departures[:min_len]
            arrivals = arrivals[:min_len]
            sources = sources[:min_len]
            durations = durations[:min_len]
            destinations = destinations[:min_len]
            fares_processed = fares_processed[:min_len]
            
            route_types_list = [route_type] * min_len
            all_buses_data = list(zip(titles, subtitles, departures, arrivals, sources, durations, destinations, fares_processed, route_types_list))
        else:
            st.warning("BS: Could not extract any consistent bus data (min_len is 0).")
            print("BS: Min_len is 0. No bus data formed.")
            all_buses_data = []
            
    except Exception as e:
        st.error(f"An unexpected error occurred in BeautifulSoup bus scraping: {e}")
        print(f"Unexpected error in BeautifulSoup bus scraping: {e}")
        print(traceback.format_exc())
    
    st.write(f"BeautifulSoup bus scraping finished. Found {len(all_buses_data)} bus entries.")
    print(f"BeautifulSoup bus scraping finished. Found {len(all_buses_data)} bus entries.")
    return all_buses_data


def load_station_codes():
    json_filepath = "stations_mapping.json" 
    try:
        with open(json_filepath, "r", encoding="utf-8") as f:
            station_code_dict = json.load(f)
        return station_code_dict
    except FileNotFoundError:
        print(f"Error: The file '{json_filepath}' was not found.")
        st.error(f"Station mapping file '{json_filepath}' not found.")
    except json.JSONDecodeError:
        print(f"Error: Failed to decode JSON from the file '{json_filepath}'.")
        st.error(f"Error decoding station mapping file '{json_filepath}'.")
    except Exception as e:
        print(f"An unexpected error occurred loading station codes: {e}")
        st.error(f"Unexpected error loading station codes: {e}")
    return {}

station_codes_names_cache = load_station_codes()

def get_station_name(code):
    return station_codes_names_cache.get(code, code)

# ---- Train Scraper (Using BeautifulSoup) ----
def scrape_trains_from_source(page_source_html, route_type):
    all_trains_data = []
    st.write("Parsing HTML with BeautifulSoup and extracting train data...")
    print("Parsing HTML with BeautifulSoup and extracting train data...")
    try:
        soup = BeautifulSoup(page_source_html, 'lxml')

        raw_train_names_bs = extract_bs_text(soup.find_all(class_="name"))
        standardized_train_types = [standardize_train_name(tn) for tn in raw_train_names_bs]
        durations_bs = extract_bs_text(soup.find_all(class_="duration"))
        
        train_time_elements_bs = soup.find_all(class_="trainTime")
        departures, arrivals, sources, destinations = [], [], [], []
    
        for element in train_time_elements_bs:
            spans = element.find_all("span") # Use find_all for BeautifulSoup
            if len(spans) >= 2:
                raw_departure_text = spans[0].get_text(strip=True)
                departure_time = raw_departure_text[:5]
                source_code = raw_departure_text[6:].strip()
                
                raw_arrival_text = spans[-2].get_text(strip=True) # Assuming same logic for span indexing
                arrival_time = raw_arrival_text[:5]
                destination_code = raw_arrival_text[6:].strip()

                departures.append(departure_time)
                arrivals.append(arrival_time)
                sources.append(get_station_name(source_code))
                destinations.append(get_station_name(destination_code))
            else:
                departures.append("N/A"); arrivals.append("N/A"); sources.append("N/A"); destinations.append("N/A")

        prices_list_final = []
        # Use select for potentially complex CSS selectors if needed, or find_all
        price_containers_bs = soup.find_all(class_="react-horizontal-scrolling-menu--scroll-container")

        for container in price_containers_bs:
            price_entries_raw = extract_bs_text(container.find_all(class_="avail-cls"))
            current_train_prices = []
            for price_entry in price_entries_raw:
                parts = price_entry.split("₹")
                if len(parts) == 2:
                    cls = parts[0].strip() 
                    try:
                        base_price = int(float(parts[1].replace(",", "").strip()))
                        extended_price = base_price + (150 if cls == "SL" else 400)
                        current_train_prices.append(f"{cls} {base_price} - {extended_price}")
                    except ValueError:
                        current_train_prices.append(price_entry)  
                else:
                    current_train_prices.append(price_entry)
            prices_list_final.append("; ".join(current_train_prices) if current_train_prices else "N/A")

        frequencies_list_final = []
        frequency_containers_bs = soup.find_all(class_="days-of-run")
        for container in frequency_containers_bs:
            running_days_elements = container.find_all(class_="running")
            running_days_text = [day.get_text(strip=True) for day in running_days_elements if day.get_text(strip=True)]
            
            if len(running_days_text) == 7:
                frequencies_list_final.append("D")
            elif running_days_text:
                frequencies_list_final.append(", ".join(running_days_text))
            else:
                frequencies_list_final.append("N/A")
        
        train_counts_msg = (f"BS Train Counts: Names={len(raw_train_names_bs)}, Types={len(standardized_train_types)}, "
                            f"Departures={len(departures)}, Arrivals={len(arrivals)}, Sources={len(sources)}, "
                            f"Durations={len(durations_bs)}, Destinations={len(destinations)}, "
                            f"Prices={len(prices_list_final)}, Frequencies={len(frequencies_list_final)}")
        print(train_counts_msg)
        st.write(train_counts_msg)

        all_data_lists_train = [raw_train_names_bs, standardized_train_types, departures, arrivals, sources, 
                                durations_bs, destinations, prices_list_final, frequencies_list_final]
        
        max_len = 0
        non_empty_train_lists = [lst for lst in all_data_lists_train if lst]
        if non_empty_train_lists:
             max_len = max(len(lst) for lst in non_empty_train_lists)
        else:
            st.warning("BS: All train data fields returned empty.")
            print("BS Warning: All train data fields returned empty.")
            return []

        if max_len > 0:
            raw_train_names_padded = raw_train_names_bs + ["N/A"] * (max_len - len(raw_train_names_bs))
            standardized_train_types_padded = standardized_train_types + ["N/A"] * (max_len - len(standardized_train_types))
            departures_padded = departures + ["N/A"] * (max_len - len(departures))
            arrivals_padded = arrivals + ["N/A"] * (max_len - len(arrivals))
            sources_padded = sources + ["N/A"] * (max_len - len(sources))
            durations_padded = durations_bs + ["N/A"] * (max_len - len(durations_bs))
            destinations_padded = destinations + ["N/A"] * (max_len - len(destinations))
            prices_list_final_padded = prices_list_final + ["N/A"] * (max_len - len(prices_list_final))
            frequencies_list_final_padded = frequencies_list_final + ["N/A"] * (max_len - len(frequencies_list_final))
            
            route_types_list = [route_type] * max_len
            all_trains_data = list(zip(raw_train_names_padded, standardized_train_types_padded, departures_padded, 
                                       arrivals_padded, sources_padded, durations_padded, destinations_padded, 
                                       prices_list_final_padded, frequencies_list_final_padded, route_types_list))
        else:
            st.warning("BS: Could not extract any consistent train data (max_len is 0).")
            print("BS: Max_len for train data is 0. No train data formed.")
            all_trains_data = []
            
    except Exception as e:
        st.error(f"Error fetching train details with BeautifulSoup: {e}")
        print(f"Error fetching train details with BeautifulSoup: {e}")
        print(traceback.format_exc())
    
    st.write(f"BeautifulSoup train scraping finished. Found {len(all_trains_data)} train entries.")
    print(f"BeautifulSoup train scraping finished. Found {len(all_trains_data)} train entries.")
    return all_trains_data

# ---- Download CSV ----
def download_csv(dataframe, filename):
    if dataframe.empty:
        st.warning(f"No data to download for {filename}.")
        return
    for col in dataframe.columns:
        dataframe[col] = dataframe[col].astype(str)
    csv_data = dataframe.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
    st.download_button(label=f"📥 Download {filename}", data=csv_data, file_name=filename, mime="text/csv", key=filename)

# ---- Page Routing ----
if page == "Home":
    st.title("🚀 Web Scraper: Bus & Train Data Extraction")
    st.write("""
    This tool uses Selenium to load the page and handle JavaScript, then passes the HTML to BeautifulSoup for faster data extraction.
    *Steps to Use:*
    1. Select *Bus Scraper 🚌* or *Train Scraper 🚆* from the left menu.
    2. Enter the URL.
    3. Click *Scrape*.
    4. Download as *CSV*.
    """)

elif page == "Bus Scraper 🚌":
    st.title("🚌 Bus Scraper")
    url_bus = st.text_input("Enter Bus Search URL:", placeholder="https://www.abhibus.com/bus_search/... ", key="bus_url_input")
    route_type_bus = st.radio("Route Type", ["Bus-Route", "Bus-Enroute"], key="bus_route_type_radio")

    if st.button("Scrape Buses", key="scrape_buses_button"):
        if url_bus:
            driver = None 
            all_bus_data_result = []
            try:
                with st.spinner("Selenium: Setting up driver, navigating, and waiting for page load..."):
                    start_time_total = time.time()
                    driver = setup_driver()
                    st.write(f"Navigating to URL: {url_bus}")
                    print(f"Navigating to URL: {url_bus}")
                    driver.get(url_bus)
                    
                    # Expand government buses (Selenium interaction)
                    expand_government_buses(driver) 
                    
                    # Wait for a sentinel element to ensure page is fully rendered AFTER expansions
                    # This is CRITICAL for the page_source to be complete.
                    st.write("Selenium: Waiting for final page content after expansions (e.g., 'span.fare')...")
                    print("Selenium: Waiting for final page content after expansions (e.g., 'span.fare')...")
                    WebDriverWait(driver, 20).until(
                        EC.presence_of_all_elements_located((By.CSS_SELECTOR, "span.fare"))
                    )
                    time.sleep(1) # Small extra pause for absolute certainty
                    st.write("Selenium: Final content detected. Getting page source.")
                    print("Selenium: Final content detected. Getting page source.")
                    page_source = driver.page_source
                
                # Scrape using BeautifulSoup from the obtained page source
                if page_source:
                    with st.spinner("BeautifulSoup: Parsing HTML and extracting bus data..."):
                        all_bus_data_result = scrape_buses_from_source(page_source, route_type_bus)
                else:
                    st.error("Failed to retrieve page source from Selenium.")
                    print("Error: page_source was empty.")

                end_time_total = time.time()
                st.success(f"Bus scraping completed in {round(end_time_total - start_time_total, 2)} seconds ⏱️ Found {len(all_bus_data_result)} buses.")
                print(f"Bus scraping completed in {round(end_time_total - start_time_total, 2)} seconds.")

                if all_bus_data_result:
                    df_bus = pd.DataFrame(all_bus_data_result, columns=["Bus Name", "Bus Type", "Departure", "Arrival", "Starting Place", "Duration", "Ending Place", "Price", "Route Type"])
                    
                    is_gov_by_std_name = df_bus["Bus Name"] == "Government Bus"
                    is_gov_by_rtc_in_name = df_bus["Bus Name"].str.contains("RTC", case=False, na=False)
                    is_gov_by_rtc_in_type = df_bus["Bus Type"].str.contains("RTC", case=False, na=False)
                
                    gov_condition = is_gov_by_std_name | is_gov_by_rtc_in_name | is_gov_by_rtc_in_type
                
                    df_gov = df_bus[gov_condition].copy()
                    df_private = df_bus[~gov_condition].copy()

                    if not df_gov.empty:
                        st.write("### Government/RTC Buses 🏛")
                        st.dataframe(df_gov)
                        download_csv(df_gov, "government_buses.csv")
                    if not df_private.empty:
                        st.write("### Private Buses 🚍")
                        st.dataframe(df_private)
                        download_csv(df_private, "private_buses.csv")
                    
                    if df_gov.empty and df_private.empty and not df_bus.empty:
                        st.write("### All Buses")
                        st.dataframe(df_bus)
                        download_csv(df_bus, "all_buses.csv")
                    elif df_bus.empty:
                         st.warning("No bus data was processed into the DataFrame from BeautifulSoup.")

                else: 
                    st.warning("No bus data extracted by BeautifulSoup. Check page source and selectors.")
            except TimeoutException as te_selenium:
                st.error(f"Selenium timed out waiting for page elements (e.g., 'span.fare' after expansions): {te_selenium}")
                print(f"Selenium TimeoutException: {te_selenium}")
                print(traceback.format_exc())
            except Exception as e:
                st.error(f"An error occurred during the bus scraping process: {e}")
                print(f"An error occurred during the bus scraping process: {e}")
                print(traceback.format_exc())
            finally:
                if driver:
                    driver.quit()
                    print("WebDriver closed for buses.")
        else:
            st.warning("⚠ Please enter a valid Bus URL.")

elif page == "Train Scraper 🚆":
    st.title("🚆 Train Scraper")
    url_train = st.text_input("Enter Train Search URL:", placeholder="https://www.abhibus.com/trains/results/...", key="train_url_input")
    route_type_train = st.radio("Route Type", ["Train-Route", "Train-Enroute"], key="train_route_type_radio")

    if st.button("Scrape Trains", key="scrape_trains_button"):
        if url_train:
            driver = None
            all_train_data_result = []
            try:
                with st.spinner("Selenium: Setting up driver, navigating, and waiting for page load..."):
                    start_time_total = time.time()
                    driver = setup_driver()
                    st.write(f"Navigating to URL: {url_train}")
                    print(f"Navigating to URL: {url_train}")
                    driver.get(url_train)
                    
                    st.write("Selenium: Waiting for final train page content (e.g., train 'name')...")
                    print("Selenium: Waiting for final train page content (e.g., train 'name')...")
                    WebDriverWait(driver, 25).until(
                        EC.presence_of_all_elements_located((By.CLASS_NAME, "name")) # Your sentinel for trains
                    )
                    time.sleep(1) 
                    st.write("Selenium: Final train content detected. Getting page source.")
                    print("Selenium: Final train content detected. Getting page source.")
                    page_source = driver.page_source

                if page_source:
                    with st.spinner("BeautifulSoup: Parsing HTML and extracting train data..."):
                        all_train_data_result = scrape_trains_from_source(page_source, route_type_train)
                else:
                    st.error("Failed to retrieve page source from Selenium for trains.")
                    print("Error: page_source was empty for trains.")
                
                end_time_total = time.time()
                st.success(f"Train scraping completed in {round(end_time_total - start_time_total, 2)} seconds ⏱️ Found {len(all_train_data_result)} trains.")
                print(f"Train scraping completed in {round(end_time_total - start_time_total, 2)} seconds.")

                if all_train_data_result:
                    df_train = pd.DataFrame(all_train_data_result, columns=["Train Name", "Train Type", "Departure", "Arrival", "Starting Station", "Duration", "Destination Station", "Prices", "Frequency", "Route Type"])
                    st.dataframe(df_train)
                    download_csv(df_train, "train_details.csv")
                else:
                    st.warning("No train data extracted by BeautifulSoup. Check page source and selectors.")
            except TimeoutException as te_selenium:
                st.error(f"Selenium timed out waiting for train page elements (e.g., 'name'): {te_selenium}")
                print(f"Selenium TimeoutException for trains: {te_selenium}")
                print(traceback.format_exc())
            except Exception as e:
                st.error(f"An error occurred during train scraping: {e}")
                print(f"An error occurred during train scraping: {e}")
                print(traceback.format_exc())
            finally:
                if driver:
                    driver.quit()
                    print("WebDriver closed for trains.")
        else:
            st.warning("⚠ Please enter a valid Train URL.")