import streamlit as st
import pandas as pd
from google.oauth2.service_account import Credentials
import gspread
from utils import *
from googleapiclient.discovery import build
import pytz
from datetime import datetime
import random
import string

sheet_id = st.secrets["general"]["sheet_id"]
DRIVE_ID = st.secrets["general"]["drive_id"]
PARENT_FOLDER_ID = st.secrets["general"]["parent_folder"]
time_sheet_id = st.secrets["general"]["time_sheet_id"]

sheets_creds = Credentials.from_service_account_info(
    st.secrets["google_sheets_credentials"],
    scopes=[
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
)

sheets_service = build('sheets', 'v4', credentials=sheets_creds)

drive_creds = Credentials.from_service_account_info(
    st.secrets["google_drive_credentials"],
    scopes=["https://www.googleapis.com/auth/drive"]
)

drive_service = build('drive', 'v3', credentials=drive_creds)

client_gcp = gspread.authorize(sheets_creds)
colombia_timezone = pytz.timezone('America/Bogota')

#--------------------------------------UTILITY FUNCTIONS--------------------------------
def clear_temp_directory():
    for root, _, files in os.walk(TEMP_DIR):
        for file_name in files:
            os.remove(os.path.join(root, file_name))

def initialize_state():
    default_values = {
        "page": "select_sales_rep",
        "sales_rep": None,
        "services": [],
        "client": None,
        "client_role": None,
        "completed": True,
        "start_time": datetime.now(colombia_timezone),
        "end_time": None,
        "uploaded_files": {},
        "temp_details": {},
        "generated_ids": set(),
        "request_id": None,
        "final_comments": "",
        "initialized": True,
    }
    for key, value in default_values.items():
        if key not in st.session_state:
            st.session_state[key] = value

    if not st.session_state.get("request_id"):
        st.session_state["request_id"] = generate_request_id()

    reset_json()
    clear_temp_directory()

def generate_request_id():
    if "generated_ids" not in st.session_state:
        st.session_state["generated_ids"] = set()

    while True:
        unique_id = "Q" + "".join(random.choices(string.digits, k=4))
        if unique_id not in st.session_state["generated_ids"]:
            st.session_state["generated_ids"].add(unique_id)
            return unique_id

def change_page(new_page):
    st.session_state["page"] = new_page

#------------------------------------APP----------------------------------------
col1, col2, col3 = st.columns([1, 2, 1])

with col2:
    st.image("logo_trading.png", width=800)

if "initialized" not in st.session_state or not st.session_state["initialized"]:
    initialize_state()

if st.session_state["completed"]:
    if "request_id" not in st.session_state or not st.session_state["request_id"]:
        st.session_state["request_id"] = generate_request_id()
        st.session_state["start_time"] = datetime.now(colombia_timezone)
    elif st.session_state.get("start_time") is None:
        st.session_state["start_time"] = datetime.now(colombia_timezone)
    
    if st.session_state.get("start_time") is None:
        st.session_state["start_time"] = datetime.now(colombia_timezone)

    request_id = st.session_state['request_id']
    start_time = st.session_state["start_time"]

    st.write(f"**Quotation ID: {request_id}**")

    if st.session_state["page"] == "select_sales_rep":

        sales_rep = st.selectbox(
            "Please select a Sales Representative",
            ["-- Sales Representative --", "Pedro Bruges", "Andrés Consuegra", "Ivan Zuluaga", "Sharon Zuñiga",
            "Johnny Farah", "Felipe Hoyos", "Jorge Sánchez",
            "Irina Paternina", "Stephanie Bruges"],
            key="commercial"
        )

        st.session_state["sales_rep"] = sales_rep

        def handle_next():
            if st.session_state["sales_rep"] == "-- Sales Representative --":
                st.warning("Please select a valid Sales Representative before proceeding.")
            else:
                change_page("client_name")

        st.button("Next", on_click=handle_next)

    elif st.session_state["page"] == "client_name":

        sales_rep = st.session_state.get("sales_rep", "-- Sales Representative --")
        st.subheader(f"Hello, {sales_rep}!")

        client = st.text_input("Who is your client?", key="client_input")
        client_role = st.radio("Client Role", ["Shipper", "Consignee"], key="role")

        def handle_next_client():
            if not client or client.strip() == "":
                st.warning("Please enter a valid client name before proceeding.")
            else:
                st.session_state["client"] = client
                st.session_state["client_role"] = client_role
                change_page("add_services")

        st.button("Next", on_click=handle_next_client)

    elif st.session_state["page"] == "add_services":

        service = st.selectbox(
                    "What service would you like to quote?",
                    ["-- Services --", "International Freight", "Ground Transportation", "Customs Brokerage"],
                    key="service"
        )

        def handle_next():
            if service == "-- Services --":
                st.warning("Please select a valid service before proceeding.")
            else:
                change_page("client_data")

        st.button("Next", on_click=handle_next)

        st.session_state["temp_details"]["service"] = service
    
    elif st.session_state["page"] == "client_data":

        service = st.session_state["temp_details"].get("service", None)
        role = st.session_state.get("client_role")

    #------------------------------------INTERNATIONAL FREIGHT----------------------------
        if service == "International Freight":
            st.subheader("International Freight")

            transport_type = st.selectbox("Transport Type", ["Maritime", "Air"], key="transport_type")
            st.session_state["temp_details"]["transport_type"] = transport_type

            if transport_type == "Air":
                modality_options = ["LCL"]
            else:
                modality_options = ["FCL", "LCL"]

            modality = st.selectbox("Modality", modality_options, key="modality")

            with st.expander("**Cargo Details**"):
                incoterms_by_role = {
                    "Shipper": ["FOB", "CIF", "DAP", "FCA", "CFR", "DDP", "CIP", "FAS", "CPT"],
                    "Consignee": ["EXW", "FOB", "CIF", "DAP", "FCA", "CFR", "CIP", "FAS", "CPT"]
                }

                incoterm_options = incoterms_by_role.get(role, [])
                if not incoterm_options:
                    st.warning("No incoterm options available for the selected role.")

                incoterm = st.selectbox("Select Incoterm", incoterm_options, key="incoterm")

                if incoterm:
                    incoterm_result = questions_by_incoterm(incoterm, st.session_state["temp_details"], service, role)

                    if isinstance(incoterm_result, tuple):
                        incoterm_details, routes = incoterm_result
                    else:
                        incoterm_details, routes = incoterm_result, []

                    if isinstance(incoterm_details, dict):
                        st.session_state["temp_details"].update(incoterm_details)

                    if routes:
                        st.session_state["routes"] = routes

            with st.expander("**Transportation Details**"):
                if modality == "FCL":
                    common_details = common_questions()
                    st.session_state["temp_details"].update(common_details)

                    if common_details.get("type_container") in ["Reefer 20'", "Reefer 40'"]:
                        st.markdown("**-----Refrigerated Cargo Details-----**")
                        refrigerated_cargo = handle_refrigerated_cargo(common_details["type_container"], incoterm)
                        st.session_state["temp_details"].update(refrigerated_cargo)
                elif modality == "LCL":
                    lcl_details = lcl_questions()
                    st.session_state["temp_details"].update(lcl_details)

            with st.expander("**Final Details**"):
                final_details = final_questions()
                st.session_state["temp_details"].update(final_details)
            
            st.button("Add Service", key="add_service", on_click=handle_add_service)

    #-----------------------------------------GROUND TRANSPORTATION-----------------------------------------
        elif service == "Ground Transportation": 
            st.subheader("Ground Transportation")

            with st.expander("**Cargo Details**"):
                lcl_details = ground_transport()
                st.session_state["temp_details"].update(lcl_details)
            
            temp_details = st.session_state.get("temp_details", {})
            with st.expander("**Final Details**"):
                final_details = final_questions()
                st.session_state["temp_details"].update(final_details)
            
            st.button("Add Service", key="add_service", on_click=handle_add_service)

        elif service == "Customs Brokerage":
            st.subheader("Customs Brokerage")

            with st.expander("**Customs Details**"):
                customs_details = customs_questions(service)
                st.session_state["temp_details"].update(customs_details)
            
            temp_details = st.session_state.get("temp_details", {})
            with st.expander("**Final Details**"):
                final_details = final_questions()
                st.session_state["temp_details"].update(final_details)
            
            st.button("Add Service", key="add_service", on_click=handle_add_service)

    elif st.session_state["page"] == "requested_services":

        if st.session_state["services"]:
            st.subheader("Requested Services")
            services = st.session_state["services"]

            def handle_edit(service_index):
                st.session_state["edit_index"] = service_index
                service = services[service_index]
                st.session_state["temp_details"] = service["details"].copy()
                st.session_state["temp_details"]["service"] = service["service"]
                change_page("client_data")

            def handle_delete(service_index):
                removed_service = st.session_state["services"].pop(service_index)
                services_json = load_services()

                updated_services = [
                    s for s in services_json
                    if s["details"] != removed_service["details"] or s["service"] != removed_service["service"]
                ]
                save_services(updated_services)
                st.success(f"Service {service_index + 1} has been removed!")

            def button(service):
                if service:
                    handle_edit(i)

            for i, service in enumerate(services):
                col1, col2, col3 = st.columns([0.8, 0.1, 0.1]) 

                with col1:
                    st.write(f"{i + 1}. {service['service']}")
                with col2:
                    st.button(
                        f"✏️",
                        key=f"edit_{i}",
                        on_click=lambda index=i: handle_edit(index)
                    )
                with col3:
                    st.button(
                        f"🗑️",
                        key=f"delete_{i}",
                        on_click=lambda index=i: handle_delete(index) 
                    )

            col1, col2 = st.columns([0.04, 0.2])

            with col1:
                def handle_add_service():
                    change_page("add_services")
                
                st.button("Add Service", on_click=handle_add_service)

            with col2:

                for df_name in ["df_freight", "df_ground_transport", "df_customs"]:
                    if df_name not in st.session_state:
                        st.session_state[df_name] = pd.DataFrame()

                if st.session_state.get("quotation_completed", False):
                    change_page("select_sales_rep")
                    st.stop() 

                def handle_finalize_quotation():
                    services = load_services()

                    if services:
                        try:
                            if "folder_id" not in st.session_state or st.session_state["folder_request_id"] != request_id:
                                folder_id, folder_link = folder(request_id)
                                st.session_state["folder_id"] = folder_id
                                st.session_state["folder_link"] = folder_link
                                st.session_state["folder_request_id"] = request_id
                            
                            folder_id = st.session_state.get("folder_id", "No folder created")

                            if not folder_id:
                                st.error("Failed to create or retrieve folder. Aborting finalization.")
                                return
                            
                            upload_all_files_to_google_drive(folder_id)
                            
                            clear_temp_directory()

                            st.session_state["end_time"] = datetime.now(colombia_timezone)
                            end_time = st.session_state["end_time"]

                            if st.session_state["start_time"] and st.session_state["end_time"]:
                                duration = (end_time - st.session_state["start_time"]).total_seconds()
                            else:
                                st.error("Start time or end time is missing. Cannot calculate duration.")
                                return
    
                            end_time_str = end_time.strftime('%Y-%m-%d %H:%M:%S')
                            log_time(st.session_state["start_time"], end_time, duration, st.session_state["request_id"])

                            commercial = st.session_state.get("sales_rep", "Unknown")
                            client = st.session_state["client"]
                            folder_link = st.session_state.get("folder_link", "N/A")

                            freight_records = []
                            ground_transport_records = []
                            customs_records = []

                            for service in services:
                                base_info = {
                                    "time": end_time_str,
                                    "request_id": f'=HYPERLINK("{folder_link}"; "{st.session_state["request_id"]}")',
                                    "commercial": commercial,
                                    "client": client,
                                    "service": service["service"],
                                }

                                if "info_pallets" in service["details"]:
                                    pallets_info = service["details"]["info_pallets"]
                                    pallets_str = "\n".join(
                                        [
                                            f"Pallet {i + 1}: "
                                            f"Weight={pallet['weight_lcl']}KG, "
                                            f"Volume={pallet['volume']:.2f}CBM, "
                                            f"Dimensions={pallet['length']}x{pallet['width']}x{pallet['height']}CM"
                                            for i, pallet in enumerate(pallets_info)
                                        ]
                                    )
                                    service["details"]["info_pallets_str"] = pallets_str
                                    del service["details"]["info_pallets"]

                                if service["service"] == "International Freight":
                                    routes = service["details"].get("routes", [])
                                    routes_str = (
                                        "\n".join(
                                            [
                                                f"Route {i + 1}: {route['origin']} - {route['destination']}"
                                                for i, route in enumerate(routes)
                                            ]
                                        )
                                        if routes
                                        else "No routes provided"
                                    )
                                    service["details"]["routes_info"] = routes_str
                                    del service["details"]["routes"]
                                else:
                                    service["details"]["routes_info"] = "Not applicable"

                                full_record = {**base_info, **service["details"]}

                                if service["service"] == "International Freight":
                                    freight_records.append(full_record)
                                elif service["service"] == "Ground Transportation":
                                    ground_transport_records.append(full_record)
                                elif service["service"] == "Customs Brokerage":
                                    customs_records.append(full_record)

                            if freight_records:
                                new_freight_df = pd.DataFrame(freight_records)
                                st.session_state["df_freight"] = pd.concat(
                                    [st.session_state.get("df_freight", pd.DataFrame()), new_freight_df],
                                    ignore_index=True
                                )
                                save_to_google_sheets(st.session_state["df_freight"], "Freight", sheet_id)

                            if ground_transport_records:
                                new_ground_transport_df = pd.DataFrame(ground_transport_records)
                                st.session_state["df_ground_transport"] = pd.concat(
                                    [st.session_state.get("df_ground_transport", pd.DataFrame()), new_ground_transport_df],
                                    ignore_index=True
                                )
                                save_to_google_sheets(st.session_state["df_ground_transport"], "Ground Transport", sheet_id)

                            if customs_records:
                                new_customs_df = pd.DataFrame(customs_records)
                                st.session_state["df_customs"] = pd.concat(
                                    [st.session_state.get("df_customs", pd.DataFrame()), new_customs_df],
                                    ignore_index=True
                                )
                                save_to_google_sheets(st.session_state["df_customs"], "Customs", sheet_id)

                            del st.session_state["request_id"]
                            st.session_state["services"] = []
                            st.session_state["start_time"] = None
                            st.session_state["end_time"] = None
                            st.session_state["quotation_completed"] = False
                            initialize_state()
                            st.session_state["page"] = "select_sales_rep"

                            st.success("Quotation completed!")
                            change_page("select_sales_rep")

                        except Exception as e:
                            st.error(f"An error occurred: {str(e)}")

                    else:
                        st.warning("No services have been added to finalize the quotation.")

                st.button("Finalize Quotation", on_click=handle_finalize_quotation)