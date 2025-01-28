import streamlit as st
from google.oauth2.service_account import Credentials
import gspread
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import os
import csv
import pytz
from datetime import datetime
import json
import os
from copy import deepcopy
import pandas as pd

SERVICES_FILE = "services.json"
TEMP_DIR = "temp_uploads"

freight_columns = [
    "request_id", "time", "commercial", "service", "client", "incoterm", "transport_type", "modality", "routes_info", "pickup_address", "zip_code_origin", "delivery_address", "zip_code_destination", 
    "commodity", "hs_code", "cargo_value", "weight", "destination_cost", 
    "type_container", "reinforced", "food_grade", "isotank", "flexitank","imo_cargo", "imo_type", "un_code", "positioning", "pickup_city", "lcl_fcl_mode", "drayage_reefer", "reefer_cont_type", "pickup_thermo_king", "temperature", "temperature_control ",
    "info_pallets_str", "lcl_description", "not_stackable",
    "final_comments"
]

transport_columns = [
    "request_id", "time", "commercial", "service", "client", "country_origin", "city_origin", "pickup_address", "zip_code_origin", "country_destination", "city_destination", "delivery_address", "zip_code_destination", "commodity", "hs_code",
    "imo_cargo", "imo_type", "un_code", "ground_service", "temperature", "cargo_value",
    "info_pallets_str", "lcl_description", "not_stackable",
    "final_comments"
]

customs_columns = [
    "request_id", "time", "commercial", "service", "client", "country_origin", "country_destination", "commodity", "hs_code", "imo_cargo", "imo_type", "un_code", "cargo_value",
    "info_pallets_str", "final_comments"
]


sheet_id = st.secrets["general"]["sheet_id"]
DRIVE_ID = st.secrets["general"]["drive_id"]
time_sheet_id = st.secrets["general"]["time_sheet_id"]
PARENT_FOLDER_ID = st.secrets["general"]["parent_folder"]

sheets_creds= Credentials.from_service_account_info(
    st.secrets["google_sheets_credentials"],
    scopes=[
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
)

sheets_service = build('sheets', 'v4', credentials=sheets_creds)

drive_creds = Credentials.from_service_account_info(
    st.secrets["google_drive_credentials"],
    scopes=["https://www.googleapis.com/auth/drive"]
)

drive_service = build('drive', 'v3', credentials=drive_creds)
client_gcp = gspread.authorize(sheets_creds)




def save_file_locally(file, temp_dir=TEMP_DIR):
    """Guarda un archivo subido en el directorio temporal."""
    try:
        temp_file_path = os.path.join(temp_dir, file.name)
        with open(temp_file_path, "wb") as temp_file:
            temp_file.write(file.read())
        return temp_file_path
    except Exception as e:
        st.error(f"Failed to save file locally: {e}")
        return None

def folder(request_id):
    if validate_shared_drive_folder(PARENT_FOLDER_ID):
        folder_id = create_folder(request_id, PARENT_FOLDER_ID)
        if not folder_id:
            st.error("Failed to create folder for this request.")
        else:
            folder_link = f"https://drive.google.com/drive/folders/{folder_id}"

    return folder_id, folder_link

def cargo(service):
    weight = None
    commercial_invoices = st.file_uploader("Attach Commercial Invoices", accept_multiple_files=True, key="commercial_invoices")
    packing_lists = st.file_uploader("Attach Packing Lists", accept_multiple_files=True, key="packing_lists")

    ci_files = []
    if commercial_invoices:
        ci_files = [save_file_locally(file) for file in commercial_invoices]

    pl_files = []
    if packing_lists:
        pl_files = [save_file_locally(file) for file in packing_lists]

    if service != "Customs Brokerage":
        weight = st.number_input("Weight", key="weight")

    return {
        "commercial_invoice_files": ci_files,
        "packing_list_files": pl_files,
        "weight": weight
    }

def dimensions():
    temp_details = st.session_state.get("temp_details", {})
    transport_type = st.session_state["temp_details"].get("transport_type", None)

    if "packages" not in st.session_state:
        st.session_state.packages = []

    def add_package():
        st.session_state.packages.append({
            "type_packaging": "Pallet",
            "quantity": 0,
            "weight_lcl": 0,
            "volume": 0.0,
            "length": 0,
            "width": 0,
            "height": 0,
            "kilovolume": 0.0
        })

    def remove_package(index):
        if 0 <= index < len(st.session_state.packages):
            del st.session_state.packages[index]

    def copy_package(index):
        if 0 <= index < len(st.session_state.packages):
            copied_package = {
                "type_packaging": st.session_state.packages[index]["type_packaging"],
                "quantity": st.session_state.packages[index]["quantity"],
                "weight_lcl": st.session_state.packages[index]["weight_lcl"],
                "volume": st.session_state.packages[index]["volume"],
                "length": st.session_state.packages[index]["length"],
                "width": st.session_state.packages[index]["width"],
                "height": st.session_state.packages[index]["height"],
                "kilovolume": st.session_state.packages[index]["kilovolume"],
            }
            st.session_state.packages.append(copied_package)
        else:
            st.error("Invalid index. Cannot copy package.")

    for i in range(len(st.session_state.packages)):
        st.markdown(f"**Package {i + 1}**")

        col1, col2, col3 = st.columns(3)
        col4, col5, col6, col7 = st.columns(4)
        col8, col9 = st.columns([0.04, 0.3])

        with col1:
            st.session_state.packages[i]["type_packaging"] = st.selectbox(
                "Packaging Type*", ["Pallet", "Box", "Bag"], 
                index=["Pallet", "Box", "Bag"].index(st.session_state.packages[i].get("type_packaging", "Pallet")),
                key=f"type_packaging_{i}"
            )
        with col2:
            st.session_state.packages[i]["quantity"] = st.number_input(
                "Quantity*", key=f"quantity_{i}", value=st.session_state.packages[i].get("quantity", 0), step=1, min_value=0)
        with col3:
            st.session_state.packages[i]["weight_lcl"] = st.number_input(
                "Weight (KG)*", key=f"weight_lcl_{i}", value=st.session_state.packages[i].get("weight_lcl", 0), step=1, min_value=0)
        with col4:
            st.session_state.packages[i]["length"] = st.number_input(
                "Length (CM)", key=f"length_{i}", value=st.session_state.packages[i].get("length", 0), step=1, min_value=0)
        with col5:
            st.session_state.packages[i]["width"] = st.number_input(
                "Width (CM)", key=f"width_{i}", value=st.session_state.packages[i].get("width", 0), step=1, min_value=0)
        with col6:
            st.session_state.packages[i]["height"] = st.number_input(
                "Height (CM)", key=f"height_{i}", value=st.session_state.packages[i].get("height", 0), step=1, min_value=0)
            
            length = st.session_state.packages[i]["length"]
            width = st.session_state.packages[i]["width"]
            height = st.session_state.packages[i]["height"]
            if length > 0 and width > 0 and height > 0:
                st.session_state.packages[i]["volume"] = (length * width * height) / 1000000 #M3

        with col7:
            if transport_type == "Air":
                st.session_state.packages[i]["kilovolume"] = st.session_state.packages[i]["volume"] * 166.6 #KV
            
            if transport_type == "Air":
                st.session_state.packages[i]["kilovolume"] = st.number_input(
                    "Kilovolume (KVM)*", key=f"kilovolume_{i}", value=st.session_state.packages[i].get("kilovolume", 0.0), step=0.1, min_value=0.0)
            else:
                st.session_state.packages[i]["volume"] = st.number_input(
                    "Volume (CBM)*", key=f"volume_{i}", value=st.session_state.packages[i].get("volume", 0.0), step=0.01, min_value=0.0)

        with col8:
            st.button("Copy", on_click=lambda i=i: copy_package(i), key=f"copy_{i}")
        with col9:
            st.button("Remove", on_click=lambda i=i: remove_package(i), key=f"remove_{i}")

    st.button("Add Package", on_click=add_package)

    return {"packages": st.session_state.packages}

def common_questions():
    temp_details = st.session_state.get("temp_details", {})
    type_container = st.selectbox(
        "Type of container*",
        [
            "20' Dry Standard",
            "40' Dry Standard",
            "40' Dry High Cube",
            "Reefer 20'",
            "Reefer 40'",
            "Open Top 20'",
            "Open Top 40'",
            "Flat Rack 20'",
            "Flat Rack 40'"
        ],
        key="type_container", index=["20' Dry Standard", "40' Dry Standard", "40' Dry High Cube", "Reefer 20'", "Reefer 40'", "Open Top 20'", "Open Top 40'", "Flat Rack 20'", "Flat Rack 40'"].index(temp_details.get("type_container", "20' Dry Standard"))
    )
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        reinforced = st.checkbox("Reinforced", key="reinforced", value=temp_details.get("reinforced", False))
    with col2:
        food_grade = st.checkbox("Foodgrade", key="food_grade", value=temp_details.get("food_grade", False))
    with col3:
        isotank = st.checkbox("Isotank", key="isotank", value=temp_details.get("isotank", False))
    with col4:
        flexitank = st.checkbox("Flexitank", key="flexitank", value=temp_details.get("flexitank", False))

    msds_files = []
    ts_files = []
    ss_files = []

    if isotank or flexitank:
        msds_files = temp_details.get("msds_files", "")
        if not msds_files:
            msds = st.file_uploader("Attach MSDS*", accept_multiple_files=True, key="msds")
            msds_files = []
            if msds:
                msds_files = [save_file_locally(file) for file in msds]

        technical_sheets = st.file_uploader("Attach Technical Sheets*", accept_multiple_files=True, key="commercial_invoices")
        ts_files = []
        if technical_sheets:
            ts_files = [save_file_locally(file) for file in technical_sheets]
        
        safety_sheets = st.file_uploader("Attach Safety Sheets*", accept_multiple_files=True, key="safety_sheets")
        ss_files = []
        if safety_sheets:
            ss_files = [save_file_locally(file) for file in safety_sheets]

    positioning = st.radio(
        "Container Positioning",
        ["In yard", "At port", "Not Applicable"],
    key="positioning", index=["In yard", "At port", "Not Applicable"].index(temp_details.get("positioning", "In yard"))
    )

    pickup_city = temp_details.get("pickup_city", "")

    if positioning == "In yard":
        pickup_city = st.text_input("Pick up City*", key="pickup_city", value=pickup_city)

    lcl_fcl_mode = st.checkbox("LCL - FCL", key="lcl_fcl_mode", value=temp_details.get("lcl_fcl_mode", False))

    return {
        "type_container": type_container,
        "reinforced": reinforced,
        "suitable_food": food_grade,
        "isotank": isotank,
        "flexitank": flexitank,
        "ts_files": ts_files,
        "ss_files": ss_files,
        "msds_files": msds_files,
        "positioning": positioning,
        "pickup_city": pickup_city,
        "lcl_fcl_mode": lcl_fcl_mode
    }

def handle_refrigerated_cargo(cont_type, incoterm):
    temp_details = st.session_state.get("temp_details", {})
    reefer_cont_type, drayage_reefer = None, None
    pickup_thermo_king, temperature = None, None

    if cont_type == "Reefer 40'":
        reefer_types = ["Controlled Atmosphere", "Cold Treatment"]
        default_index = reefer_types.index(temp_details.get("reefer_type", "Controlled Atmosphere"))
        reefer_cont_type = st.radio("Specify the type", reefer_types, 
                                    index=default_index, key="reefer_cont_type")
        temperature = st.number_input("Temperature range °C", key="temperature", value=temp_details.get("temperature", None))

    if incoterm in ["EXW", "DDP", "DAP"]:
        pickup_thermo_king = st.checkbox("Thermo King Pick up", 
                                    key="pickup_thermo_king", value=temp_details.get("pickup_thermo_king", False))

        drayage_reefer = st.checkbox("Drayage Reefer", 
                                    key="drayage_reefer", value=temp_details.get("drayage_reefer", False))
        return {
            "temperature": temperature,
            "reefer_cont_type": reefer_cont_type,
            "pickup_thermo_king": pickup_thermo_king,
            "drayage_reefer": drayage_reefer
        }

    return {
        "temperature": temperature,
        "reefer_cont_type": reefer_cont_type,
        "pickup_thermo_king": pickup_thermo_king,
    }

def insurance_questions():
    commercial_invoice = st.file_uploader("Attach Commercial Invoices", accept_multiple_files=True, key="commercial_invoices")

    ci_files = []
    if commercial_invoice:
        ci_files = [save_file_locally(file) for file in commercial_invoice]

    return {
        "commercial_invoice_files": ci_files
    }

def imo_questions():
    temp_details = st.session_state.get("temp_details", {})
    imo_cargo = st.checkbox(
        "IMO", 
        key="imo_cargo", 
        value=temp_details.get("imo_cargo", False)
    )
    un_code, msds_files, imo_type = None, None, None

    if imo_cargo:
        col1, col2 = st.columns(2)
        with col1:
            imo_type = st.text_input("IMO type*", key="imo_type", value=temp_details.get("imo_type", ""))
        with col2:
            un_code = st.text_input("UN Code*", key="un_code", value=temp_details.get("un_code", ""))
        msds = st.file_uploader("Attach MSDS*", accept_multiple_files=True, key="msds_tank")

        msds_files = []
        
        if msds:
            msds_files = [save_file_locally(file) for file in msds]

    return {
        "imo_cargo": imo_cargo,
        "imo_type": imo_type,
        "un_code": un_code,
        "msds_files": msds_files
    }

#------------------------ ROUTES MARITIME --------------------------
def initialize_routes():
    if "routes" not in st.session_state:
        st.session_state["routes"] = [{"origin": "", "destination": ""}]

def add_route():
    st.session_state["routes"].append({"origin": "", "destination": ""})

def handle_routes(transport_type):
    initialize_routes()

    if transport_type == "Air":
        csv_data = st.session_state.get("cities_csv", {})
        route_options = csv_data.get("country_city", []).tolist() 
    elif transport_type == "Maritime":
        csv_data = st.session_state.get("ports_csv", {})
        route_options = csv_data.get("port_country", []).tolist() 
    else:
        csv_data = {}
        route_options = []

    def handle_remove_route(index):
        if 0 <= index < len(st.session_state["routes"]):
            del st.session_state["routes"][index]

    def handle_add_route():
        add_route()

    cols = st.columns([0.45, 0.45, 0.1]) 

    for i, route in enumerate(st.session_state["routes"]):

        with cols[0]:
            route["origin"] = st.selectbox(
                f"Origin {i + 1}*",
                options=[""] + route_options,
                key=f"origin_{i}",
                index=route_options.index(route["origin"]) + 1
                if route["origin"] in route_options else 0,
            )
        with cols[1]:
            route["destination"] = st.selectbox(
                f"Destination {i + 1}*",
                options=[""] + route_options,
                key=f"destination_{i}",
                index=route_options.index(route["destination"]) + 1
                if route["destination"] in route_options else 0,
            )

        with cols[2]:
            st.write("")
            st.write("")
            st.button(
                "**X**", on_click=lambda i=i: handle_remove_route(i), key=f"remove_route_{i}", use_container_width=True
            )

    st.button("Add other route", on_click=handle_add_route)


def questions_by_incoterm(incoterm, details, service, transport_type):

    routes_formatted = []
    if details is None:
        details = {}

    handle_routes(transport_type)
    routes = st.session_state.get("routes", [])
    routes_formatted = [
        {"origin": route["origin"], "destination": route["destination"]}
        for route in routes ]

    commodity = st.text_input("Commodity*", key="commodity", value=details.get("commodity", ""))

    p_imo = imo_questions()
    details.update(p_imo)      

    pickup_address = details.get("pickup_address", None)
    zip_code_origin = details.get("zip_code_origin", None)
    customs_origin = details.get("customs_origin", False)
    delivery_address = details.get("delivery_address", None)
    zip_code_destination = details.get("zip_code_destination", None)
    insurance_required = details.get("insurance_required", False)
    cargo_value = details.get("cargo_value", None)
    hs_code = details.get("hs_code", None)
    customs_info = {}
    destination_cost = details.get("destination_cost", False)

    if incoterm in ["FCA", "EXW", "DDP", "DAP"]:
        hs_code = st.text_input("HS Code*", key="hs_code", value=details.get("hs_code", ""))
        if incoterm in ["DDP", "DAP", "EXW"]:
            pickup_address = st.text_input("Pickup Address*", key="pickup_address", value=pickup_address)
        else: 
            pickup_address = st.text_input("Pickup Address", key="pickup_address", value=pickup_address)
        zip_code_origin = st.text_input("Zip Code City of Origin", key="zip_code_origin", value=zip_code_origin)

        if incoterm == "FCA":
            st.write("Under this term, the responsibility for customs clearance at origin typically lies with the shipper. However, in certain cases, the consignee assumes this responsibility. In our quotation, we include the origin costs when applicable.")
            customs_origin = st.checkbox("Quote customs at origin", key="customs_origin", value=customs_origin)

            if customs_origin:
                customs_info = customs_questions(service, customs=True)

        if incoterm in ["EXW", "DDP", "DAP"]:
            if incoterm in ["DDP", "DAP"]:
                delivery_address = st.text_input("Delivery Address*", key="delivery_address", value=delivery_address)
            elif incoterm == "EXW":
                delivery_address = st.text_input("Delivery Address", key="delivery_address", value=delivery_address)
            zip_code_destination = st.text_input("Zip Code City of Destination", key="zip_code_destination", value=zip_code_destination)
            cargo_value = st.number_input("Cargo Value (USD)*", key="cargo_value", value=details.get("cargo_value", 0))
            customs_info = customs_questions(service, customs=True)
            
            destination_cost = st.checkbox("Quote surcharges at destination", key="destination_cost", value=details.get("destination_cost", False))

    elif incoterm in ["CIF", "CFR"]:
        hs_code = st.text_input("HS Code", key="hs_code", value=details.get("hs_code", ""))
        destination_cost = st.checkbox("Quote surcharges at destination", key="destination_cost", value=details.get("destination_cost", False))

    elif incoterm == "FOB":
        hs_code = st.text_input("HS Code", key="hs_code", value=details.get("hs_code", ""))

    insurance_required = st.checkbox("Insurance Required", key="insurance_required", value=insurance_required)
    if insurance_required:
        if incoterm not in ["EXW", "DDP", "DAP", "FCA"]:
            cargo_value = st.number_input("Cargo Value (USD)*", key="cargo_value", value=details.get("cargo_value", 0))
            if not customs_origin:
                insurance = insurance_questions()
                details.update(insurance)

    if incoterm == "FCA" and insurance_required or customs_origin:
        cargo_value = st.number_input("Cargo Value (USD)*", key="cargo_value", value=details.get("cargo_value", 0))

    details["destination_cost"] = destination_cost

    details.update({
        "incoterm": incoterm,
        "routes": routes_formatted,
        "commodity": commodity,
        "hs_code": hs_code,
        **p_imo,
        "pickup_address": pickup_address,
        "zip_code_origin": zip_code_origin,
        "delivery_address": delivery_address,
        "zip_code_destination": zip_code_destination,
        "cargo_value": cargo_value,
        **customs_info,
        "customs_origin": customs_origin,
        "insurance_required": insurance_required,
    })

    return details, routes


def ground_transport():
    temp_details = st.session_state.get("temp_details", {})
    data = st.session_state.get("cities_csv", [])
    countries = data["Country"].dropna().unique().tolist()

    col1, col2 = st.columns(2)
    with col1:
        country_origin = st.selectbox("Country of Origin*", options=[""] + countries, key="country_origin",
            index=(countries.index(temp_details.get("country_origin", "")) + 1)
            if temp_details.get("country_origin", "") in countries else 0,
        )

    filtered_cities = []
    if country_origin:
        filtered_cities = (data[data["Country"] == country_origin]["City"].dropna().unique().tolist())

    with col2:
        city_origin = st.selectbox("City of Origin*", options=[""] + filtered_cities, key="city_origin",
            index=(filtered_cities.index(temp_details.get("city_origin", "")) + 1)
            if temp_details.get("city_origin", "") in filtered_cities else 0,
        )

    pickup_address = st.text_input("Pickup Address*", key="pickup_address", value=temp_details.get("pickup_address", ""))
    zip_code_origin = st.text_input("Zip Code City of Origin", key="zip_code_origin", value=temp_details.get("zip_code_origin", ""))

    col1, col2 = st.columns(2)
    with col1:
        country_destination = st.selectbox(
            "Country of Destination*", options=[""] + countries, key="country_destination",
            index=(countries.index(temp_details.get("country_destination", "")) + 1)
            if temp_details.get("country_destination", "") in countries else 0,
        )

    filtered_cities_destination = []
    if country_destination:
        filtered_cities_destination = (data[data["Country"] == country_destination]["City"].dropna().unique().tolist())

    with col2:
        city_destination = st.selectbox("City of Destination*", options=[""] + filtered_cities_destination, key="city_destination",
            index=(filtered_cities_destination.index(temp_details.get("city_destination", "")) + 1)
            if temp_details.get("city_destination", "") in filtered_cities_destination else 0,
        )

    delivery_address = st.text_input("Delivery Address*", key="delivery_address", value=temp_details.get("delivery_address", ""))
    zip_code_destination = st.text_input("Zip Code City of Destination", key="zip_code_destination", value=temp_details.get("zip_code_destination", ""))

    commodity = st.text_input("Commodity*", key="commodity", value=temp_details.get("commodity", ""))
    hs_code = st.text_input("HS Code", key="hs_code", value=temp_details.get("hs_code", ""))
    imo = imo_questions()
    cargo_value = st.number_input("Cargo Value (USD)*", key="cargo_value", value=temp_details.get("cargo_value", 0))
    
    temperature, dimensions_info = None, None

    ground_service = st.selectbox(
            "Select Ground Service*",
            [
                "Drayage 20 STD", "Drayage 40 STD/40 HC", "FTL 53 FT", "Flat Bed", "Box Truck",
                "Drayage Reefer 20 STD", "Drayage Reefer 40 STD", "Tractomula", "Mula Refrigerada", "LTL"
            ],
            key="ground_service",
            index=[
                "Drayage 20 STD", "Drayage 40 STD/40 HC", "Dryvan", "Flat Bed", "Box Truck",
                "Drayage Reefer 20 STD", "Drayage Reefer 40 STD", "Tractomula", "Mula Refrigerada", "LTL"
            ].index(temp_details.get("ground_service", "Drayage 20 STD"))
        )
    
    if ground_service in ["Mula Refrigerada", "Drayage Reefer 20 STD", "Drayage Reefer 40 STD"]:
        temperature = st.number_input(
            "Temperature range °C*", key="temperature", value=temp_details.get("temperature", None))
        return {
            "country_origin": country_origin,
            "city_origin": city_origin,
            "country_destination": country_destination,
            "city_destination": city_destination,
            "pickup_address": pickup_address,
            "zip_code_origin": zip_code_origin,
            "delivery_address": delivery_address,
            "zip_code_destination": zip_code_destination,
            "commodity": commodity,
            "hs_code": hs_code,
            **imo,
            "cargo_value": cargo_value,
            "ground_service": ground_service,
            "temperature": temperature
        }
    if ground_service == "LTL":
        dimensions_info = dimensions() or {}
        return {
            "country_origin": country_origin,
            "city_origin": city_origin,
            "country_destination": country_destination,
            "city_destination": city_destination,
            "pickup_address": pickup_address,
            "zip_code_origin": zip_code_origin,
            "delivery_address": delivery_address,
            "zip_code_destination": zip_code_destination,
            "commodity": commodity,
            "hs_code": hs_code,
            **imo,
            "cargo_value": cargo_value,
            "ground_service": ground_service,
            "temperature": temperature,
            **dimensions_info
        }

    return {
        "country_origin": country_origin,
        "city_origin": city_origin,
        "country_destination": country_destination,
        "city_destination": city_destination,
        "pickup_address": pickup_address,
        "zip_code_origin": zip_code_origin,
        "delivery_address": delivery_address,
        "zip_code_destination": zip_code_destination,
        "commodity": commodity,
        "hs_code": hs_code,
        "ground_service": ground_service
    }

def lcl_questions(transport_type):
    temp_details = st.session_state.get("temp_details", {})
    temperature, temperature_control, stackable = None, None, None

    dimensions_info = dimensions()

    if transport_type == "Air":
        temperature_control = st.checkbox(
            "Temperature control required",
            key="temperature_control",
            value=temp_details.get("temperature_control", False)
        )
        if temperature_control:
            temperature = st.text_input(
                "Temperature range °C*",
                key="temperature",
                value=temp_details.get("temperature", "")
            )

        stackable = st.checkbox(
        "Not stackable",
        key="not_stackable",
        value=temp_details.get("not_stackable", False)
    )

    lcl_description = st.text_area(
        "Relevant Information",
        key="lcl_description",
        value=temp_details.get("lcl_description", "")
    )

    return {
        **dimensions_info,
        "temperature_control": temperature_control,
        "temperature": temperature,
        "lcl_description": lcl_description,
        "stackable": stackable
    }

def customs_questions(service, customs=False):
    temp_details = st.session_state.get("temp_details", {})
    data = st.session_state.get("cities_csv", [])
    countries = data["Country"].dropna().unique().tolist()
    customs_data = {}
    if not customs:
        col1, col2 = st.columns(2)
        with col1:
            country_origin = st.selectbox("Country of Origin*", options=[""] + countries, key="country_origin",
                index=(countries.index(temp_details.get("country_origin", "")) + 1)
                if temp_details.get("country_origin", "") in countries else 0,
            )
        with col2:
            country_destination = st.selectbox(
            "Country of Destination", options=[""] + countries, key="country_destination",
            index=(countries.index(temp_details.get("country_destination", "")) + 1)
            if temp_details.get("country_destination", "") in countries else 0,
        )
        commodity = st.text_input("Commodity*", key="commodity", value=temp_details.get("commodity", ""))
        hs_code = st.text_input("HS Code*", key="hs_code", value=temp_details.get("hs_code", ""))
        imo = imo_questions()
        cargo_value = st.number_input("Cargo Value (USD)*", key="cargo_value", value=temp_details.get("cargo_value", 0))

        dimensions_info = dimensions()
        customs_data.update({
            "country_origin": country_origin,
            "country_destination": country_destination,
            "commodity": commodity,
            "hs_code": hs_code,
            "cargo_value": cargo_value,
            **imo,
            **dimensions_info,
        })

    cargo_info = cargo(service)
    origin_certificates = st.file_uploader("Certificate of Origin", accept_multiple_files=True, key="origin_certificates")

    origin_certificate_files = []
    if origin_certificates:
        origin_certificate_files = [save_file_locally(file) for file in origin_certificates]

    customs_data.update({
        **cargo_info,
        "origin_certificate_files": origin_certificate_files,
    })
    return customs_data

def final_questions():
    temp_details = st.session_state.get("temp_details", {})

    final_comments = st.text_area("Final Comments", key="final_comments", value=temp_details.get("final_comments", ""))
    st.session_state["temp_details"]["final_comments"] = final_comments

    additional_documents = st.file_uploader("Attach Additional Documents", accept_multiple_files=True, key="additional_documents_files")

    additional_documents_files = []
    if additional_documents:
        additional_documents_files = [save_file_locally(file) for file in additional_documents]

    return {
        "final_comments": final_comments,
        "additional_documents_files": additional_documents_files
    }

def validate_service_details(temp_details):
    errors = []

    if not isinstance(temp_details, dict):
        errors.append("The 'temp_details' object is missing or not properly initialized.")
        return errors

    service = temp_details.get("service", "")
    modality = temp_details.get("modality")
    hs_code = temp_details.get("hs_code", "")
    commodity = temp_details.get("commodity")
    imo = temp_details.get("imo_cargo", False)
    transport_type = temp_details.get("transport_type", "")

    if not commodity:
        errors.append("Commodity is required.")
    if imo:
        imo_type = temp_details.get("imo_type", "")
        un_code = temp_details.get("un_code", "")
        msds_files = temp_details.get("msds_files", "")
        if not msds_files:
            errors.append("MSDS is required.")
        if not imo_type:
            errors.append("IMO type is required.")
        if not un_code:
            errors.append("UN Code is required.")

    if service == "International Freight":
        insurance_required = temp_details.get("insurance_required", False)
        if insurance_required:
            cargo_value = temp_details.get("cargo_value", 0) or 0
            if cargo_value <= 0:
                errors.append("Cargo value is required.")

        routes = temp_details.get("routes", [])
        if not routes:
            errors.append("At least one route is required.")
        else:
            for idx, route in enumerate(routes):
                if not route.get("origin"):
                    errors.append(f"The origin of route {idx + 1} is required.")
                if not route.get("destination"):
                    errors.append(f"The destination of route {idx + 1} is required.")

        if modality == "FCL":
            positioning = temp_details.get("positioning", "")
            if positioning == "In yard":
                pickup_city = temp_details.get("pickup_city", "")
                if not pickup_city:
                    errors.append("Pick up city is required.")

        incoterm = temp_details.get("incoterm", "")
        if incoterm in ["FCA", "EXW", "DDP", "DAP"]:
            hs_code = temp_details.get("hs_code", "")
            cargo_value = temp_details.get("cargo_value", 0) or 0
            if cargo_value <= 0:
                errors.append("Cargo value is required.")
            if not hs_code:
                errors.append("HS Code is required.")
            if incoterm in ["EXW","DDP", "DAP"]:
                pickup_address = temp_details.get("pickup_address", "")
                if not pickup_address:
                    errors.append("Pick up Address is required.")
                if incoterm != "EXW":
                    delivery_address = temp_details.get("delivery_address", "")
                    if not delivery_address:
                        errors.append("Delivery address is required.")
        
        isotank = temp_details.get("isotank", False)
        flexitank = temp_details.get("flexitank", False)

        if isotank or flexitank:
            msds_files = temp_details.get("msds_files", "")
            ts_files = temp_details.get("ts_files", "")
            ss_files = temp_details.get("ss_files", "")
            if not msds_files:
                errors.append("MSDS is required.")
            if not ts_files:
                errors.append("Technical Sheet is required.")
            if not ss_files:
                errors.append("Safety Sheet is required.")

        if modality == "LCL":
            packages = temp_details.get("packages", [])
            if not packages:
                errors.append("At least one package is required for LCL modality.")
            else:
                if transport_type == "Air":
                    for idx, package in enumerate(packages):
                        if package.get("quantity", 0) <= 0:
                            errors.append(f"The quantity of package {idx + 1} must be greater than 0.")
                        if package.get("weight_lcl", 0) <= 0 and package.get("kilovolume", 0) <= 0:
                            errors.append(f"The weight or kilovolume of package {idx + 1} must be greater than 0.")
                        if package.get("weight_lcl", 0) > 0 and package.get("kilovolume", 0) > 0:
                            continue
                        if (
                            package.get("length", 0) <= 0 or 
                            package.get("width", 0) <= 0 or 
                            package.get("height", 0) <= 0
                        ):
                            errors.append(f"The dimensions of package {idx + 1} must be greater than 0 if weight and kilovolume are not specified.")
                else:
                    for idx, package in enumerate(packages):
                        if package.get("quantity", 0) <= 0:
                            errors.append(f"The quantity of package {idx + 1} must be greater than 0.")
                        if package.get("weight_lcl", 0) <= 0 and package.get("volume", 0) <= 0:
                            errors.append(f"The weight or volume of package {idx + 1} must be greater than 0.")
                        if package.get("weight_lcl", 0) > 0 and package.get("volume", 0) > 0:
                            continue
                        if (
                            package.get("length", 0) <= 0 or 
                            package.get("width", 0) <= 0 or 
                            package.get("height", 0) <= 0
                        ):
                            errors.append(f"The dimensions of package {idx + 1} must be greater than 0 if weight and volume are not specified.")

    elif service == "Ground Transportation":
        pickup_address = temp_details.get("pickup_address","")
        delivery_address = temp_details.get("delivery_address", "")
        country_origin = temp_details.get("country_origin", "")
        country_destination = temp_details.get("country_destination", "")
        city_origin = temp_details.get("city_origin", "")
        city_destination = temp_details.get("city_destination", "")
        cargo_value = temp_details.get("cargo_value", 0)

        if not country_origin:
            errors.append("Country of Origin is required.")
        if not city_origin:
            errors.append("City of Origin is required.")
        if not country_destination:
            errors.append("Country of Destination is required.")
        if not city_destination:
            errors.append("City of Destination is required.")
        if not pickup_address:
            errors.append("Pick up address is required.")
        if not delivery_address:
            errors.append("Delivery address is required.")
        if cargo_value == 0:
            errors.append("Cargo value is required.")

        imo = temp_details.get("imo_cargo", False)
        if imo:
            imo_type = temp_details.get("imo_type", "")
            un_code = temp_details.get("un_code", "")
            if not imo_type:
                errors.append("IMO type is required.")
            if not un_code:
                errors.append("UN Code is required.")

    elif service == "Customs Brokerage":
        country_origin = temp_details.get("country_origin", [])
        country_destination = temp_details.get("country_destination", [])
        hs_code = temp_details.get("hs_code", "")

        if not country_origin:
            errors.append("Origin Country is required.")
        if not country_destination:
            errors.append("Destination Country is required.")
        if not hs_code:
            errors.append("HS Code is required.")

        packages = temp_details.get("packages", [])
        if not packages:
            errors.append("At least one package is required.")
        else:
            for idx, package in enumerate(packages):
                if package.get("quantity", 0) <= 0:
                    errors.append(f"The quantity of package {idx + 1} must be greater than 0.")
                if package.get("weight_lcl", 0) <= 0 and package.get("volume", 0) <= 0:
                    errors.append(f"The weight or volume of package {idx + 1} must be greater than 0.")
                if package.get("weight_lcl", 0) > 0 and package.get("volume", 0) > 0:
                    continue
                if (
                    package.get("length", 0) <= 0 or 
                    package.get("width", 0) <= 0 or 
                    package.get("height", 0) <= 0
                ):
                    errors.append(f"The dimensions of package {idx + 1} must be greater than 0 if weight and volume are not specified.")

    return errors


def handle_add_service():
    prefill_temp_details()
    temp_details = st.session_state.get("temp_details", {})
    if not temp_details:
        st.warning("Please provide the service details before adding.")
        return
    
    service = temp_details.get("service")
    if not service or service == "-- Services --":
        st.warning("Please enter a valid service before proceeding.")
        return

    services = st.session_state.get("services", [])
    edit_index = st.session_state.get("edit_index")

    if edit_index is not None:
        if 0 <= edit_index < len(services):
            st.session_state["services"][edit_index] = {
                "service": service,
                "details": temp_details
            }
            st.success("Service successfully updated.")
            del st.session_state["edit_index"]
        else:
            st.warning("Invalid edit index.")
    else:
        validation_errors = validate_service_details(temp_details)
        if validation_errors:
            for error in validation_errors:
                st.error(error)
            return
        else:
            new_service = {
                "service": service,
                "details": temp_details
            }
            st.session_state["services"].append(new_service)
            st.success("Service successfully added.")

    save_services(st.session_state["services"])
    st.session_state["temp_details"] = {}
    change_page("requested_services")


def change_page(new_page):
    st.session_state["page"] = new_page

def save_to_google_sheets(dataframe, sheet_name, sheet_id, max_attempts=5):
    attempts = 0

    while attempts < max_attempts:
        try:
            sheet = client_gcp.open_by_key(sheet_id)
            try:
                worksheet = sheet.worksheet(sheet_name)
                if worksheet.row_count == 0:
                    if sheet_name == "Freight":
                        worksheet.append_row([col.upper() for col in freight_columns])
                    elif sheet_name == "Ground Transport":
                        worksheet.append_row([col.upper() for col in transport_columns])
                    elif sheet_name == "Customs":
                        worksheet.append_row([col.upper() for col in customs_columns])

            except gspread.exceptions.WorksheetNotFound:
                worksheet = sheet.add_worksheet(title=sheet_name, rows="10000", cols="50")
                if sheet_name == "Freight":
                    worksheet.append_row([col.upper() for col in freight_columns])
                elif sheet_name == "Ground Transport":
                    worksheet.append_row([col.upper() for col in transport_columns])
                elif sheet_name == "Customs":
                    worksheet.append_row([col.upper() for col in customs_columns])

            if sheet_name == "Freight":
                dataframe = dataframe.reindex(columns=freight_columns)
            elif sheet_name == "Ground Transport":
                dataframe = dataframe.reindex(columns=transport_columns)
            elif sheet_name == "Customs":
                dataframe = dataframe.reindex(columns=customs_columns)

            dataframe.columns = dataframe.columns.str.upper()
            new_data = dataframe.fillna("").values.tolist()
            worksheet.append_rows(new_data, table_range="A2")
            
            return

        except Exception as e:
            attempts += 1
            st.error(f"Attempt {attempts}/{max_attempts}: Failed to save data to Google Sheets: {e}")
            if attempts == max_attempts:
                st.error("Maximum retry attempts reached. Unable to save data.")
                raise e

def validate_shared_drive_folder(parent_folder_id):
    try:
        folder = drive_service.files().get(
            fileId=parent_folder_id,
            fields='id',
            supportsAllDrives=True
        ).execute()
        return folder is not None
    except Exception as e:
        st.error(f"Parent folder not found or inaccessible: {e}")
        return False

def get_folder_id(folder_name, parent_folder_id):
    try:
        query = f"name = '{folder_name}' and mimeType = 'application/vnd.google-apps.folder' and '{parent_folder_id}' in parents and trashed = false"
        response = drive_service.files().list(
            q=query,
            spaces='drive',
            fields='files(id, name)',
            supportsAllDrives=True
        ).execute()
        files = response.get('files', [])
        if files:
            return files[0]['id']
        return None
    except Exception as e:
        st.error(f"Failed to search for folder: {e}")
        return None

def create_folder(folder_name, parent_folder_id):
    existing_folder_id = get_folder_id(folder_name, parent_folder_id)
    if existing_folder_id:
        st.info(f"Folder '{folder_name}' already exists with ID: {existing_folder_id}")
        return existing_folder_id

    try:
        file_metadata = {
            'name': folder_name,
            'mimeType': 'application/vnd.google-apps.folder',
            'parents': [parent_folder_id]
        }
        folder = drive_service.files().create(
            body=file_metadata,
            fields='id',
            supportsAllDrives=True
        ).execute()
        
        folder_id = folder.get('id')

        return folder_id
    
    except Exception as e:
        st.error(f"Failed to create folder: {e}")
        return None, None

def log_time(start_time, end_time, duration, request_id):
    sheet_name = "Timestamp"
    try:
        sheet = client_gcp.open_by_key(time_sheet_id)
        try:
            worksheet = sheet.worksheet(sheet_name)
            start_time_str = start_time.strftime('%Y-%m-%d %H:%M:%S')
            end_time_str = end_time.strftime('%Y-%m-%d %H:%M:%S')
            worksheet.append_row([request_id, start_time_str, end_time_str, duration])
        
        except gspread.exceptions.WorksheetNotFound:
            worksheet = sheet.add_worksheet(title=sheet_name, rows="1000", cols="20")
            worksheet.append_row(["request_id","Start Time", "End Time", "Duration (seconds)"])
            start_time_str = start_time.strftime('%Y-%m-%d %H:%M:%S')
            end_time_str = end_time.strftime('%Y-%m-%d %H:%M:%S')
            worksheet.append_row([request_id, start_time_str, end_time_str, duration])

    except Exception as e:
        st.error(f"Failed to save data to Google Sheets: {e}")

def load_services():
    if os.path.exists(SERVICES_FILE):
        with open(SERVICES_FILE, "r") as file:
            return json.load(file)
    return []

def save_services(services):
    with open(SERVICES_FILE, "w") as file:
        json.dump(services, file, indent=4)

def reset_json():
    if os.path.exists(SERVICES_FILE):
        os.remove(SERVICES_FILE)
    with open(SERVICES_FILE, "w") as file:
        json.dump([], file)

if not os.path.exists(TEMP_DIR):
    os.makedirs(TEMP_DIR)

def save_file_locally(file, temp_dir=TEMP_DIR):
    try:
        temp_file_path = os.path.join(temp_dir, file.name)
        with open(temp_file_path, "wb") as temp_file:
            temp_file.write(file.read())
        return temp_file_path
    except Exception as e:
        st.error(f"Failed to save file locally: {e}")
        return None


def handle_file_uploads(file_uploader_key, label="Attach Files*", temp_dir=TEMP_DIR):
    os.makedirs(temp_dir, exist_ok=True)

    if file_uploader_key not in st.session_state:
        st.session_state[file_uploader_key] = {}

    uploaded_files = st.file_uploader(label, accept_multiple_files=True, key=file_uploader_key)

    if uploaded_files:
        for uploaded_file in uploaded_files:
            if uploaded_file.name not in st.session_state[file_uploader_key]:
                file_path = save_file_locally(uploaded_file, temp_dir=temp_dir)
                if file_path:
                    st.session_state[file_uploader_key][uploaded_file.name] = file_path

    current_uploaded_files = set(
        [file.name for file in uploaded_files] if uploaded_files else []
    )
    session_uploaded_files = set(st.session_state[file_uploader_key].keys())

    files_to_remove = session_uploaded_files - current_uploaded_files
    for file_name in files_to_remove:
        file_path = st.session_state[file_uploader_key].pop(file_name, None)
        if file_path and os.path.exists(file_path):
            os.remove(file_path)

    return list(st.session_state[file_uploader_key].values())

def upload_all_files_to_google_drive(folder_id):
    try:
        for root, _, files in os.walk(TEMP_DIR):
            for file_name in files:
                file_path = os.path.join(root, file_name)
                with open(file_path, "rb") as file:
                    file_metadata = {
                        'name': file_name,
                        'parents': [folder_id]
                    }
                    media = MediaFileUpload(file_path, resumable=True)

                    uploaded_file = drive_service.files().create(
                        body=file_metadata,
                        media_body=media,
                        fields='id, webViewLink',
                        supportsAllDrives=True
                    ).execute()

    except Exception as e:
        st.error(f"Failed to upload files to Google Drive: {e}")

def load_existing_ids_from_sheets():
    sheet_name = "Timestamp"
    while True: 
        try:
            sheet = client_gcp.open_by_key(time_sheet_id)

            worksheet_list = [ws.title for ws in sheet.worksheets()]
            if sheet_name not in worksheet_list:
                return set()

            worksheet = sheet.worksheet(sheet_name)
            existing_ids = worksheet.col_values(1)
            return set(existing_ids[1:]) 

        except gspread.exceptions.SpreadsheetNotFound:
            st.error("The spreadsheet with the provided ID was not found. Retrying...")

        except gspread.exceptions.WorksheetNotFound:
            st.error(f"The worksheet '{sheet_name}' was not found in the spreadsheet. Retrying...")

        except Exception as e:
            st.error(f"Error while loading IDs from Google Sheets: {e}. Retrying...")

def go_back():
    navigation_flow = [
        "select_sales_rep",
        "client_name",
        "add_services",
        "client_data",
        "requested_services"
    ]
    current_page = st.session_state.get("page", "select_sales_rep")
    if current_page in navigation_flow:
        current_index = navigation_flow.index(current_page)
        if current_index > 0: 
            st.session_state["page"] = navigation_flow[current_index - 1]

def load_shared_values_from_services():
    services = load_services()
    shared_values = {}

    for service in services:
        details = service.get("details", {})
        for key, value in details.items():
            if key in shared_values and shared_values[key] != value:
                continue
            shared_values[key] = value

    return shared_values

def prefill_temp_details():
    shared_values = load_shared_values_from_services()
    temp_details = st.session_state.get("temp_details", {})

    for key, value in shared_values.items():
        if key not in temp_details: 
            temp_details[key] = value

    st.session_state["temp_details"] = temp_details
