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
@st.cache_data(ttl=3600)
def clear_temp_directory():
    for root, _, files in os.walk(TEMP_DIR):
        for file_name in files:
            os.remove(os.path.join(root, file_name))

@st.cache_data(ttl=3600)
def load_csv(file):
    df = pd.read_csv(file)
    return df

def initialize_state():
    default_values = {
        "page": "select_sales_rep",
        "sales_rep": None,
        "services": [],
        "client": None,
        "client_reference": None,
        "completed": True,
        "start_time": datetime.now(colombia_timezone),
        "end_time": None,
        "uploaded_files": {},
        "temp_details": {"routes": [], "packages": [], "dimensions_flatrack": []},
        "generated_ids": set(),
        "request_id": None,
        "final_comments": "",
        "initialized": True,
        "ports_csv": None,
        "cities_csv": None
    }
    for key, value in default_values.items():
        if key not in st.session_state:
            st.session_state[key] = value

    if not st.session_state.get("request_id"):
        st.session_state["request_id"] = generate_request_id()

    reset_json()
    clear_temp_directory()

    if st.session_state["ports_csv"] not in st.session_state:
        try:
            st.session_state["ports_csv"] = load_csv("output_port_world.csv")
        except Exception as e:
            st.error("Error loading CSV data. Please check the file path or format.")

    if st.session_state["cities_csv"] not in st.session_state:
        try:
            st.session_state["cities_csv"] = load_csv("cities_world.csv")
        except Exception as e:
            st.error("Error loading CSV data. Please check the file path or format.")

    if "uploaded_files" not in st.session_state:
        st.session_state.uploaded_files = []
    
    if "submitted" not in st.session_state:
        st.session_state["submitted"] = False

def generate_request_id():
    if "generated_ids" not in st.session_state:
        st.session_state["generated_ids"] = set()

    existing_ids = load_existing_ids_from_sheets()

    while True:
        unique_id = "Q" + "".join(random.choices(string.digits, k=4))
        if unique_id not in st.session_state["generated_ids"] and unique_id not in existing_ids:
            st.session_state["generated_ids"].add(unique_id)
            return unique_id

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
            "Please select a Sales Representative*",
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

        client = st.text_input("Who is your client?*", key="client_input")
        reference = st.text_input("Client reference", key="reference")

        def handle_next_client():
            if not client or client.strip() == "":
                st.warning("Please enter a valid client name before proceeding.")
            else:
                st.session_state["client"] = client
                st.session_state["client_reference"] = reference
                change_page("add_services")

        col1, col2 = st.columns([0.04, 0.3])
        with col1:
            st.button("Back", on_click=go_back, key="back_client_name") 
        with col2:
            st.button("Next", on_click=handle_next_client)

    elif st.session_state["page"] == "add_services":

        service = st.selectbox(
                    "What service would you like to quote?*",
                    ["-- Services --", "International Freight", "Ground Transportation", "Customs Brokerage"],
                    key="service"
        )

        def handle_next():
            if service == "-- Services --":
                st.warning("Please select a valid service before proceeding.")
            else:
                st.session_state["temp_details"]["service"] = service
                change_page("client_data")

        col1, col2 = st.columns([0.04, 0.3])
        with col1:
            st.button("Back", on_click=go_back, key="back_choose_service") 
        with col2:
            st.button("Next", on_click=handle_next)
    
    elif st.session_state["page"] == "client_data":

        service = st.session_state["temp_details"].get("service", None)

        prefill_temp_details()
        temp_details = st.session_state["temp_details"]

    #------------------------------------INTERNATIONAL FREIGHT----------------------------
        if service == "International Freight":
            st.subheader("International Freight")

            transport_type = st.selectbox("Transport Type*", ["Maritime", "Air"], key="transport_type")
            st.session_state["temp_details"]["transport_type"] = transport_type

            if transport_type == "Air":
                modality_options = ["LCL"]
            else:
                modality_options = ["FCL", "LCL"]

            modality = st.selectbox("Modality*", modality_options, key="modality")
            st.session_state["temp_details"]["modality"] = modality

            if "cargo_details_expander" not in st.session_state:
                st.session_state["cargo_details_expander"] = True
            if "transportation_details_expander" not in st.session_state:
                st.session_state["transportation_details_expander"] = True
            if "final_details_expander" not in st.session_state:
                st.session_state["final_details_expander"] = True

            with st.expander("**Cargo Details**", expanded=st.session_state["cargo_details_expander"]):

                incoterms_op = {
                    "Maritime": ["FOB", "FCA", "CIF", "CFR", "EXW", "DDP", "DAP", "CPT"],
                    "Air": ["FOB", "DDP", "DAP", "CIP", "CPT", "EXW"]
                }

                incoterm_options = incoterms_op.get(transport_type, [])

                incoterm = st.selectbox("Select Incoterm*", incoterm_options, key="incoterm")

                if incoterm:
                    incoterm_result = questions_by_incoterm(incoterm, st.session_state["temp_details"], service, transport_type)

                    if isinstance(incoterm_result, tuple):
                        incoterm_details, routes = incoterm_result
                    else:
                        incoterm_details, routes = incoterm_result, []

                    if isinstance(incoterm_details, dict):
                        st.session_state["temp_details"].update(incoterm_details)

                    if routes:
                        st.session_state["routes"] = routes

            with st.expander("**Transportation Details**", expanded=st.session_state["transportation_details_expander"]):
                if modality == "FCL":
                    common_details = common_questions()
                    st.session_state["temp_details"].update(common_details)

                    reefer_containers = [ct for ct in common_details.get("type_container", []) if ct in ["Reefer 40'", "Reefer 20'"]]
                    if reefer_containers:
                        st.markdown("**-----Refrigerated Cargo Details-----**")
                        refrigerated_cargo = handle_refrigerated_cargo(reefer_containers, incoterm)
                        st.session_state["temp_details"].update(refrigerated_cargo)
                if modality == "LCL":
                    lcl_details = lcl_questions(transport_type)
                    st.session_state["temp_details"].update(lcl_details)

            with st.expander("**Final Details**", expanded=st.session_state["final_details_expander"]):
                final_details = final_questions()
                st.session_state["temp_details"].update(final_details)
            
            col1, col2 = st.columns([0.04, 0.3])
            with col1:
                st.button("Back", on_click=go_back, key="back_service") 
            with col2:
                st.button("Add Service", key="add_service", on_click=handle_add_service)

    #-----------------------------------------GROUND TRANSPORTATION-----------------------------------------
        elif service == "Ground Transportation": 
            st.subheader("Ground Transportation")

            if "cargo_details_expander" not in st.session_state:
                st.session_state["cargo_details_expander"] = True
            if "final_details_expander" not in st.session_state:
                st.session_state["final_details_expander"] = True

            with st.expander("**Cargo Details**", expanded=st.session_state["cargo_details_expander"]):
                lcl_details = ground_transport()
                st.session_state["temp_details"].update(lcl_details)
            
            temp_details = st.session_state.get("temp_details", {})
            with st.expander("**Final Details**", expanded=st.session_state["final_details_expander"]):
                final_details = final_questions()
                st.session_state["temp_details"].update(final_details)

            col1, col2 = st.columns([0.04, 0.3])
            with col1:
                st.button("Back", on_click=go_back, key="back_service") 
            with col2:
                st.button("Add Service", key="add_service", on_click=handle_add_service)

        elif service == "Customs Brokerage":
            st.subheader("Customs Brokerage")

            if "customs_details_expander" not in st.session_state:
                st.session_state["customs_details_expander"] = True
            if "final_details_expander" not in st.session_state:
                st.session_state["final_details_expander"] = True

            with st.expander("**Customs Details**", expanded=st.session_state["customs_details_expander"]):
                customs_details = customs_questions(service)
                st.session_state["temp_details"].update(customs_details)
            
            temp_details = st.session_state.get("temp_details", {})
            with st.expander("**Final Details**", expanded=st.session_state["final_details_expander"]):
                final_details = final_questions()
                st.session_state["temp_details"].update(final_details)

            col1, col2 = st.columns([0.04, 0.3])
            with col1:
                st.button("Back", on_click=go_back, key="back_service") 
            with col2:
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
                #save_services(updated_services)
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
                if not st.session_state["services"]:
                    change_page("select_sales_rep")

            def button(service):
                if service:
                    handle_edit(i)

            for i, service in enumerate(services):
                col1, col2, col3 = st.columns([0.8, 0.1, 0.1]) 
                service_name = service.get("service", "Unknown Service")

                with col1:
                    st.write(f"{i + 1}. {service_name}")
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

            col1, col2 = st.columns([0.04, 0.1])

            with col1:
                def handle_another_service():
                    change_page("add_services")
                st.button("Add Another Service", on_click=handle_another_service)

            with col2:
                with col2:
                    if "df_all_quotes" not in st.session_state:
                        st.session_state["df_all_quotes"] = pd.DataFrame()

                    if st.session_state.get("quotation_completed", False):
                        st.session_state.clear()
                        change_page("select_sales_rep")
                        st.stop()

                    def handle_finalize_quotation():
                        if st.session_state.get("submitted", False):
                            st.warning("This quotation has already been submitted.")
                            return

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
                                client_reference = st.session_state.get("client_reference", "N/A")
                                folder_link = st.session_state.get("folder_link", "N/A")

                                grouped_record = {
                                    "time": end_time_str,
                                    "request_id": f'=HYPERLINK("{folder_link}"; "{st.session_state["request_id"]}")',
                                    "commercial": commercial,
                                    "client": client,
                                    "client_reference": client_reference,
                                    "service": set(),
                                    "routes_info": set(),
                                    "type_container": set(),
                                    "container_characteristics": set(),
                                    "imo": set(),
                                    "info_flatrack": set(),
                                    "info_pallets_str": set(),
                                    "reefer_details": [],
                                    "additional_costs": []
                                }

                                all_details = {}

                                for service in services:
                                    details = service["details"]
                                    grouped_record["service"].add(service["service"]) 

                                    if "type_container" in details:
                                        if isinstance(details["type_container"], list):
                                            grouped_record["type_container"].update(details["type_container"])  # Agregar múltiples valores únicos
                                        else:
                                            grouped_record["type_container"].add(details["type_container"])  # Agregar un solo valor único

                                    # Convertir el set en una lista y unir los valores con saltos de línea
                                    grouped_record["type_container"] = "\n".join(sorted(grouped_record["type_container"]))

                                    # **1️⃣ Características del Contenedor**
                                    characteristics = []
                                    if details.get("reinforced", False):
                                        characteristics.append("Reinforced")
                                    if details.get("food_grade", False):
                                        characteristics.append("Food Grade")
                                    if details.get("isotank", False):
                                        characteristics.append("Isotank")
                                    if details.get("flexitank", False):
                                        characteristics.append("Flexitank")
                                    
                                    if characteristics:
                                        grouped_record["container_characteristics"].add("\n".join(characteristics))

                                    # **2️⃣ Información IMO**
                                    imo_info = "Sí, IMO Type: {imo_type}, UN Code: {un_code}".format(
                                        imo_type=details.get("imo_type", "N/A"),
                                        un_code=details.get("un_code", "N/A")
                                    ) if details.get("imo_cargo", False) else "No"
                                    grouped_record["imo"].add(imo_info)

                                    # **3️⃣ Información de Rutas**
                                    if "routes" in details:
                                        routes = details["routes"]
                                        if len(routes) == 1:
                                            grouped_record["country_origin"] = routes[0]["country_origin"]
                                            grouped_record["country_destination"] = routes[0]["country_destination"]
                                            grouped_record["routes_info"].add(f"Route 1: {routes[0]['country_origin']} ({routes[0]['port_origin']}) → {routes[0]['country_destination']} ({routes[0]['port_destination']})")
                                        else:
                                            for i, r in enumerate(routes):
                                                grouped_record["routes_info"].add(
                                                    f"Route {i + 1}: {r['country_origin']} ({r['port_origin']}) → {r['country_destination']} ({r['port_destination']})"
                                                )

                                    # **4️⃣ Información de Paquetes**
                                    if "packages" in details:
                                        pallets_info = details.get("packages", [])
                                        transport_type = details.get("transport_type", "") 

                                        unique_pallets = set() 

                                        for i, p in enumerate(pallets_info):
                                            pallet_str = (
                                                f"Package {i + 1}: Type: {p['type_packaging']}, Quantity: {p['quantity']}, "
                                                f"Weight: {p['weight_lcl']}KG, "
                                                f"Volume: {p.get('volume', 0):.2f}{' KVM' if transport_type == 'Air' else ' CBM'}, "
                                                f"Dimensions: {p['length']}x{p['width']}x{p['height']}CM"
                                            )
                                            unique_pallets.add(pallet_str) 

                                        if unique_pallets:
                                            grouped_record["info_pallets_str"].add("\n".join(sorted(unique_pallets)))


                                    # **5️⃣ Información de Flatrack**
                                    if "dimensions_flatrack" in details:
                                        flatrack_info = details.get("dimensions_flatrack", [])
                                        flatrack_str = "\n".join(
                                            f"Weight: {f['weight']}KG, Dimensions: {f['length']}x{f['width']}x{f['height']}CM"
                                            for f in flatrack_info
                                        )
                                        grouped_record["info_flatrack"].add(flatrack_str)

                                    # **6️⃣ Reefer Details (Freight & Ground Refrigerado)**
                                    reefer_containers = ["Reefer 20'", "Reefer 40'"]
                                    reefer_ground_services = ["Mula Refrigerada", "Drayage Reefer 20 STD", "Drayage Reefer 40 STD"]
                                    reefer_details = []

                                    container_type = details.get("type_container", [])
                                    ground_service = details.get("ground_service", "")
                                    is_reefer_container = any(ct in reefer_containers for ct in container_type)

                                    if not is_reefer_container and ground_service not in reefer_ground_services:
                                        grouped_record["reefer_details"] = "No reefer details"
                                    else:
                                        if details.get("drayage_reefer", False):  
                                            reefer_details.append("Drayage Reefer Required")

                                        if details.get("pickup_thermo_king", False):  
                                            reefer_details.append("Thermo King Pickup Required")

                                        if details.get("reefer_cont_type"):  
                                            reefer_details.append(f"Reefer Container Type: {details['reefer_cont_type']}")

                                        if details.get("temperature_control", False):  
                                            reefer_details.append("Temperature Control Required")

                                        if details.get("temperature"):  
                                            reefer_details.append(f"Temperature Range: {details['temperature']}°C")

                                        grouped_record["reefer_details"] = "\n".join(reefer_details) if reefer_details else "No reefer details"

                                    if isinstance(grouped_record["reefer_details"], list):
                                        grouped_record["reefer_details"] = "\n".join(grouped_record["reefer_details"])

                                    # **6️⃣ Additional Costs (destination_cost + customs_origin)**
                                    additional_costs = []

                                    if details.get("destination_cost", False):
                                        additional_costs.append("Destination Cost Required")

                                    if details.get("customs_origin", False):
                                        additional_costs.append("Customs at Origin Required")

                                    if details.get("insurance_required", False):
                                        additional_costs.append("Insurance Required")

                                    grouped_record["additional_costs"] = "\n".join(additional_costs) if additional_costs else "No additional costs"

                                    # **7️⃣ Agregar detalles adicionales**
                                    for key, value in details.items():
                                        if key in ["reinforced", "food_grade", "isotank", "flexitank", "imo_cargo", "imo_type", "un_code", "routes", "packages", 
                                                "dimensions_flatrack", "customs_origin", "destination_cost", "type_container"]:
                                            continue
                                        if value is None or value == "" or (isinstance(value, (int, float)) and value == 0):
                                            continue
                                        if isinstance(value, bool):
                                            value = "Sí" if value else "No"

                                        if key in all_details:
                                            all_details[key].add(str(value))
                                        else:
                                            all_details[key] = {str(value)}

                                # **8️⃣ Convertir sets a cadenas separadas por saltos de línea**
                                for key in ["service", "container_characteristics", "imo", "routes_info", "info_pallets_str", "info_flatrack"]:
                                    grouped_record[key] = "\n".join(sorted(grouped_record[key])) if grouped_record[key] else ""

                                for key, value_set in all_details.items():
                                    grouped_record[key] = "\n".join(sorted(value_set))

                                # **9️⃣ Crear DataFrame y guardar**
                                new_df = pd.DataFrame([grouped_record])
                                new_df = new_df.reindex(columns=all_quotes_columns, fill_value="")

                                st.session_state["df_all_quotes"] = pd.concat(
                                    [st.session_state.get("df_all_quotes", pd.DataFrame()), new_df],
                                    ignore_index=True
                                )

                                save_to_google_sheets(st.session_state["df_all_quotes"], sheet_id)

                                del st.session_state["request_id"]
                                upload_all_files_to_google_drive(folder_id, drive_service)
                                clear_temp_directory()
                                reset_json()
                                st.session_state["services"] = []
                                st.session_state["start_time"] = None
                                st.session_state["end_time"] = None
                                st.session_state["quotation_completed"] = False
                                st.session_state["page"] = "select_sales_rep"
                                st.success("Quotation completed!")
                                st.session_state.clear()
                                change_page("select_sales_rep")

                            except Exception as e:
                                st.error(f"An error occurred: {str(e)}")

                        else:
                            st.warning("No services have been added to finalize the quotation.")

                st.button("Finalize Quotation", on_click=handle_finalize_quotation)