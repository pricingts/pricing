import streamlit as st
import pandas as pd
from google.oauth2.service_account import Credentials
import gspread
from utils import *
from googleapiclient.discovery import build
import time
import pytz
from datetime import datetime

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

def initialize_state():
    if "page" not in st.session_state:
        st.session_state["page"] = "select_sales_rep"
    if "sales_rep" not in st.session_state:
        st.session_state["sales_rep"] = None
    if "services" not in st.session_state:
        st.session_state["services"] = []
    if "client" not in st.session_state: 
        st.session_state["client"] = None
    if "completed" not in st.session_state:
        st.session_state["completed"] = True

def initialize_temp_details():
    if "temp_details" not in st.session_state:
        st.session_state["temp_details"] = {} 

def change_page(new_page):
    st.session_state["page"] = new_page

#------------------------------------APP----------------------------------------

initialize_state()
initialize_temp_details()

if "request_id" not in st.session_state:
    timestamp = int(time.time() * 1000)
    st.session_state["request_id"] = f"Q{timestamp}"

if "uploaded_files" not in st.session_state:
    st.session_state["uploaded_files"] = {}

if "sales_rep" not in st.session_state:
    st.session_state["sales_rep"] = "-- Sales Representative --"

request_id = st.session_state["request_id"]

col1, col2, col3 = st.columns([1, 2, 1])

with col2:
    st.image("logo_trading.png", width=800)

if st.session_state["completed"]:

    start_time = datetime.now(colombia_timezone)

    st.write(f"**Quotation ID: {request_id}**")

    if st.session_state["page"] == "select_sales_rep":

        sales_rep = st.selectbox(
            "Please select a Sales Representative",
            ["-- Sales Representative --", "Pedro Bruges", "Andrés Consuegra", "Ivan Zuluaga", "Sharon Zuñiga",
            "Johnny Farah", "Felipe Hoyos", "Jorge Sánchez", "Andrés Hoyos",
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

        def handle_next_client():
            if not client or not client:
                st.warning("Please enter a valid client name before proceeding.")
            else:
                st.session_state["client"] = client
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

        service = st.session_state["temp_details"]["service"]

        if "folder_id" not in st.session_state or st.session_state["folder_request_id"] != request_id:
            folder_id, folder_link = folder(request_id)
            st.session_state["folder_id"] = folder_id
            st.session_state["folder_link"] = folder_link
            st.session_state["folder_request_id"] = request_id
        
        folder_id = st.session_state.get("folder_id", "No folder created")

    #------------------------------------INTERNATIONAL FREIGHT----------------------------
        if service == "International Freight":
            st.subheader("International Freight")
            
            transport_type = st.selectbox("Transport Type", ["Maritime", "Air"], key="transport_type")
            st.session_state["temp_details"]["transport_type"] = transport_type

            modality = st.selectbox("Modality", ["FCL", "LCL"], key="modality")
            st.session_state["temp_details"]["modality"] = modality

            if modality == "FCL": #FCL
                with st.expander("**Cargo Details**"):

                    common_details = common_questions(folder_id)
                    st.session_state["temp_details"].update(common_details)

                    if common_details["type_container"] in ["Reefer 20'", "Reefer 40'"]:
                        st.markdown("**-----Refrigerated Cargo Details-----**")
                        refrigerated_cargo = handle_refrigerated_cargo(common_details["type_container"])
                        st.session_state["temp_details"].update(refrigerated_cargo)

                with st.expander("**Incoterm Selection**"):
                    incoterm = st.selectbox(
                        "Select Incoterm",
                        ["EXW", "FOB", "CIF", "DAP", "FCA", "CFR", "DDP"],
                        key="incoterm"
                    )

                    if incoterm:
                        incoterm_details = questions_by_incoterm(incoterm, st.session_state["temp_details"], folder_id)
                        st.session_state["temp_details"].update(incoterm_details)

                def handle_add_service():
                    if not service.strip(): 
                        st.warning("Please enter a valid service before proceeding.")
                    elif not st.session_state["temp_details"]: 
                        st.warning("Please provide the service details before adding.")
                    else:
                        st.session_state["services"].append({"service": service, "details": st.session_state["temp_details"]})
                        st.success("Service successfully added.")
                        st.session_state["temp_details"] = {}
                        change_page("requested_services")

                st.button("Add Service", key="add_service", on_click=handle_add_service)

            if modality == "LCL": # LCL
                with st.expander("**Cargo Details**"):
                    lcl_details = lcl_questions(folder_id, service)
                    st.session_state["temp_details"].update(lcl_details)

                with st.expander("**Incoterm Selection and Specific Questions**"):
                    incoterm = st.selectbox(
                        "Select Incoterm",
                        ["EXW", "FOB", "CIF", "DAP", "FCA", "CFR", "DDP"],
                        key="incoterm"
                    )
                    if incoterm:
                        incoterm_details = questions_by_incoterm(incoterm, st.session_state["temp_details"], folder_id)
                        st.session_state["temp_details"].update(incoterm_details)

                def handle_add_service():
                    if not service.strip(): 
                        st.warning("Please enter a valid service before proceeding.")
                    elif not st.session_state["temp_details"]: 
                        st.warning("Please provide the service details before adding.")
                    else:
                        st.session_state["services"].append({"service": service, "details": st.session_state["temp_details"]})
                        st.success("Service successfully added.")
                        st.session_state["temp_details"] = {}
                        change_page("requested_services")

                st.button("Add Service", key="add_service", on_click=handle_add_service)

    #-----------------------------------------GROUND TRANSPORTATION-----------------------------------------
        elif service == "Ground Transportation": 
            st.subheader("Ground Transportation")

            with st.expander("**Cargo Details**"):
                lcl_details = lcl_questions(folder_id, service)
                st.session_state["temp_details"].update(lcl_details)

            with st.expander("**Incoterm Selection and Specific Questions**"):
                incoterm = st.selectbox(
                    "Select Incoterm",
                    ["EXW", "FOB", "CIF", "DAP", "FCA", "CFR", "DDP"],
                    key="incoterm"
                )

                if incoterm:
                    incoterm_details = questions_by_incoterm(incoterm, st.session_state["temp_details"], folder_id)
                    st.session_state["temp_details"].update(incoterm_details)

            def handle_add_service():
                    if not service.strip(): 
                        st.warning("Please enter a valid service before proceeding.")
                    elif not st.session_state["temp_details"]: 
                        st.warning("Please provide the service details before adding.")
                    else:
                        st.session_state["services"].append({"service": service, "details": st.session_state["temp_details"]})
                        st.success("Service successfully added.")
                        st.session_state["temp_details"] = {}
                        change_page("requested_services")

            st.button("Add Service", key="add_service", on_click=handle_add_service)

        elif service == "Customs Brokerage":
            st.subheader("Customs Brokerage")

            with st.expander("**Customs Details**"):
                customs_details = customs_questions(folder_id, service)
                st.session_state["temp_details"].update(customs_details)

            def handle_add_service():
                    if not service.strip(): 
                        st.warning("Please enter a valid service before proceeding.")
                    elif not st.session_state["temp_details"]: 
                        st.warning("Please provide the service details before adding.")
                    else:
                        st.session_state["services"].append({"service": service, "details": st.session_state["temp_details"]})
                        st.success("Service successfully added.")
                        st.session_state["temp_details"] = {}
                        change_page("requested_services")

            st.button("Add Service", key="add_service", on_click=handle_add_service)

    elif st.session_state["page"] == "requested_services":

        if st.session_state["services"]:
            st.subheader("Requested Services")

            col1, col2 = st.columns(2)

            with col1:
                for idx, service in enumerate(st.session_state["services"]):
                    st.write(f"{idx + 1}. {service['service']}")
            
            with col2:
                for idx, service in enumerate(st.session_state["services"]):
                    st.button(f"Edit Service", key=f"edit_button_{idx}")

            col1, col2 = st.columns(2)

            with col1:
                def handle_add_service():
                    change_page("add_services")
                
                st.button("Add Service", on_click=handle_add_service)

            with col2: 

                if "df_freight" not in st.session_state:
                    st.session_state["df_freight"] = pd.DataFrame()

                if "df_ground_transport" not in st.session_state:
                    st.session_state["df_ground_transport"] = pd.DataFrame()

                if "df_customs" not in st.session_state:
                    st.session_state["df_customs"] = pd.DataFrame()

                if st.button("Finalize Quotation"):
                    if st.session_state["services"]:

                        end_time = datetime.now(colombia_timezone)
                        duration = (end_time - start_time).total_seconds()
                        end_time_str = end_time.strftime('%Y-%m-%d %H:%M:%S')
                        log_time(start_time, end_time, duration)

                        commercial = st.session_state.get("sales_rep", "Unknown")
                        client = st.session_state["client"]
                        folder_link = st.session_state.get("folder_link", "N/A")

                        freight_records = []
                        ground_transport_records = []
                        customs_records = []

                        for service in st.session_state["services"]:
                            base_info = {
                                "time": end_time_str,
                                "request_id": f'=HYPERLINK("{folder_link}"; "{request_id}")',
                                "commercial": commercial,
                                "client": st.session_state["client"],
                                "service": service["service"],
                            }

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
                                [st.session_state["df_freight"], new_freight_df],
                                ignore_index=True
                            )
                            save_to_google_sheets(st.session_state["df_freight"], "Freight", sheet_id)

                        if ground_transport_records:
                            new_ground_transport_df = pd.DataFrame(ground_transport_records)
                            st.session_state["df_ground_transport"] = pd.concat(
                                [st.session_state["df_ground_transport"], new_ground_transport_df],
                                ignore_index=True
                            )
                            save_to_google_sheets(st.session_state["df_ground_transport"], "Ground Transport", sheet_id)

                        if customs_records:
                            new_customs_df = pd.DataFrame(customs_records)
                            st.session_state["df_customs"] = pd.concat(
                                [st.session_state["df_customs"], new_customs_df],
                                ignore_index=True
                            )
                            save_to_google_sheets(st.session_state["df_customs"], "Customs", sheet_id)
                        

                        del st.session_state["request_id"]
                        st.session_state["services"] = []

                        st.success("Quotation completed!")

                    else:
                        st.warning("No services have been added to finalize the quotation.")