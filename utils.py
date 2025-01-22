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

SERVICES_FILE = "services.json"
TEMP_DIR = "temp_uploads"

freight_columns = [
    "request_id", "time", "commercial", "service", "client", "client_role", "incoterm", "transport_type", "modality", "routes_info", "pickup_address", "zip_code_origin", "delivery_address", "zip_code_destination", 
    "commodity", "hs_code", "cargo_value", "freight_cost", "insurance_cost", "weight", "destination_cost", 
    "type_container", "reinforced", "suitable_food", "imo_cargo", "un_code", "msds", "positioning", "pickup_city", "lcl_fcl_mode", "drayage_reefer", "reefer_cont_type", "pickup_thermo_king",
    "number_pallets_input", "info_pallets_str", "pallets_links", "lcl_description", "not_stackable",
    "final_comments"
]

transport_columns = [
    "request_id", "time", "commercial", "service", "client", "pickup_address", "zip_code_origin", "delivery_address", "zip_code_destination", "commodity", "hs_code",
    "ground_service", "temperature",
    "number_pallets_input", "info_pallets_str", "pallets_links", "lcl_description", "not_stackable",
    "final_comments"
]

customs_columns = [
    "request_id", "time", "commercial", "service", "client", "country_origin", "country_destination", "commodity", "hs_code", "freight_cost", 
    "number_pallets", "info_pallets_str", "insurance_cost",
    "final_comments"
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
            "height": 0
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
                "height": st.session_state.packages[index]["height"]
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
                "Packaging Type", ["Pallet", "Box", "Bag"], 
                index=["Pallet", "Box", "Bag"].index(st.session_state.packages[i].get("type_packaging", "Pallet")),
                key=f"type_packaging_{i}"
            )
        with col2:
            st.session_state.packages[i]["quantity"] = st.number_input(
                "Quantity", key=f"quantity_{i}", value=st.session_state.packages[i].get("quantity", 0), step=1, min_value=0)
        with col3:
            st.session_state.packages[i]["weight_lcl"] = st.number_input(
                "Weight (KG)", key=f"weight_lcl_{i}", value=st.session_state.packages[i].get("weight_lcl", 0), step=1, min_value=0)
        with col4:
            st.session_state.packages[i]["volume"] = st.number_input(
                "Volume (CBM)", key=f"volume_{i}", value=st.session_state.packages[i].get("volume", 0.0), step=0.01, min_value=0.0)
        with col5:
            st.session_state.packages[i]["length"] = st.number_input(
                "Length (CM)", key=f"length_{i}", value=st.session_state.packages[i].get("length", 0), step=1, min_value=0)
        with col6:
            st.session_state.packages[i]["width"] = st.number_input(
                "Width (CM)", key=f"width_{i}", value=st.session_state.packages[i].get("width", 0), step=1, min_value=0)
        with col7:
            st.session_state.packages[i]["height"] = st.number_input(
                "Height (CM)", key=f"height_{i}", value=st.session_state.packages[i].get("height", 0), step=1, min_value=0)
        with col8:
            st.button("Copy", on_click=lambda i=i: copy_package(i), key=f"copy_{i}")
        with col9:
            st.button("Remove", on_click=lambda i=i: remove_package(i), key=f"remove_{i}")

    st.button("Add Package", on_click=add_package)

    return {"packages": st.session_state.packages}


def add_route():
    st.session_state["routes"].append({"origin": "", "destination": ""})

def common_questions():
    temp_details = st.session_state.get("temp_details", {})
    type_container = st.selectbox(
        "Type of container",
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
    reinforced = st.checkbox("Reinforced", key="reinforced", value=temp_details.get("reinforced", False))
    suitable_food = st.checkbox("Suitable for foodstuffs", key="suitable_food", value=temp_details.get("suitable_food", False))

    p_imo = imo_questions()

    positioning = st.radio(
        "Container Positioning",
        ["In yard", "At port", "Not Applicable"],
    key="positioning", index=["In yard", "At port", "Not Applicable"].index(temp_details.get("positioning", "In yard"))
    )

    pickup_city = temp_details.get("pickup_city", "")

    if positioning == "In yard":
        pickup_city = st.text_input("Pickup City", key="pickup_city", value=pickup_city)

    lcl_fcl_mode = st.checkbox("LCL-FCL", key="lcl_fcl_mode", value=temp_details.get("lcl_fcl_mode", False))

    return {
        "type_container": type_container,
        "reinforced": reinforced,
        "suitable_food": suitable_food,
        **p_imo,
        "positioning": positioning,
        "pickup_city": pickup_city,
        "lcl_fcl_mode": lcl_fcl_mode
    }

def handle_refrigerated_cargo(cont_type, incoterm):
    temp_details = st.session_state.get("temp_details", {})
    reefer_cont_type, drayage_reefer = None, None
    pickup_thermo_king = None

    if cont_type == "Reefer 40'":
        reefer_types = ["Controlled Atmosphere", "Cold Treatment"]
        default_index = reefer_types.index(temp_details.get("reefer_type", "Controlled Atmosphere"))
        reefer_cont_type = st.radio("Specify the type", reefer_types, 
                                    index=default_index, key="reefer_cont_type")

    if incoterm in ["EXW", "DDP", "DAP"]:
        pickup_thermo_king = st.checkbox("Thermo King Pick up", 
                                    key="pickup_thermo_king", value=temp_details.get("pickup_thermo_king", False))

        if incoterm in ["DDP", "DAP"]:
            drayage_reefer = st.checkbox("Drayage Reefer", 
                                        key="drayage_reefer", value=temp_details.get("drayage_reefer", False))
        return {
        "reefer_cont_type": reefer_cont_type,
        "pickup_thermo_king": pickup_thermo_king,
        "drayage_reefer": drayage_reefer
    }

    return {
        "reefer_cont_type": reefer_cont_type,
        "pickup_thermo_king": pickup_thermo_king,
    }

def insurance_questions():
    technical_sheets = st.file_uploader("Attach technical sheets", accept_multiple_files=True, key="technical_sheets")

    ts_files = []
    if technical_sheets:
        ts_files = [save_file_locally(file) for file in technical_sheets]

    return {
        "technical_sheets_files": ts_files
    }

def imo_questions():
    temp_details = st.session_state.get("temp_details", {})
    imo_cargo = st.checkbox(
        "IMO", 
        key="imo_cargo", 
        value=temp_details.get("imo_cargo", False)
    )
    un_code, msds_files = None, None

    if imo_cargo:
        un_code = st.text_input("UN Code", key="un_code", value=temp_details.get("un_code", ""))
        msds = st.file_uploader("Attach MSDS", accept_multiple_files=True, key="msds")

        msds_files = []
        
        if msds:
            msds_files = [save_file_locally(file) for file in msds]

    return {
        "imo_cargo": imo_cargo,
        "un_code": un_code,
        "msds_files": msds_files
    }

def initialize_routes():
    if "routes" not in st.session_state:
        st.session_state["routes"] = [{"origin": "", "destination": ""}]

def add_route():
    st.session_state["routes"].append({"origin": "", "destination": ""})

def handle_routes():
    initialize_routes()

    def handle_remove_route(index):
        if 0 <= index < len(st.session_state["routes"]):
            del st.session_state["routes"][index]

    def handle_add_route():
        add_route()

    cols = st.columns([0.45, 0.45, 0.1]) 

    for i, route in enumerate(st.session_state["routes"]):

        with cols[0]:
            route["origin"] = st.text_input(
                f"Port of Origin {i + 1}", key=f"origin_{i}", value=route["origin"]
            )
        with cols[1]:
            route["destination"] = st.text_input(
                f"Port of Destination {i + 1}", key=f"destination_{i}", value=route["destination"]
            )
        with cols[2]:
            st.write("")
            st.write("")
            st.button(
                "**X**", on_click=lambda i=i: handle_remove_route(i), key=f"remove_route_{i}", use_container_width=True
            )

    st.button("Add other route", on_click=handle_add_route)

def questions_by_incoterm(incoterm, details, service, role):
    routes_formatted = []

    if details is None:
        details = {}

    if role == "Consignee":  # IMPORTATION
        if incoterm in ["EXW", "FCA", "FOB", "CFR", "CIF", "FAS", "DAP", "CIP", "CPT"]:
            if incoterm in ["EXW", "FCA", "FOB", "FAS", "CIP", "CPT", "CFR"]:
                handle_routes()
                routes = st.session_state.get("routes", [])
                routes_formatted = [
                {"origin": route["origin"], "destination": route["destination"]}
                for route in routes]
            
            if incoterm not in ["CIF", "DAP", "FCA", "CFR", "CIP", "FAS", "CPT"]:
                pickup_address = st.text_input("Pickup Address", key="pickup_address", value=details.get("pickup_address", ""))
                details["pickup_address"] = pickup_address

                zip_code_origin = st.text_input("Zip Code City of Origin", key="zip_code_origin", value=details.get("zip_code_origin", ""))
                details["zip_code_origin"] = zip_code_origin

            if incoterm in ["DDP", "EXW", "FOB", "CIF", "FCA", "CFR", "CIP", "FAS", "CPT"]:
                delivery_address = st.text_input("Delivery Address", key="delivery_address", value=details.get("delivery_address", ""))
                zip_code_destination = st.text_input("Zip Code City of Destination", key="zip_code_destination", value=details.get("zip_code_destination", ""))
                details.update({"delivery_address": delivery_address, "zip_code_destination": zip_code_destination})

            commodity = st.text_input("Commodity", key="commodity", value=details.get("commodity", ""))
            hs_code = st.text_input("HS Code", key="hs_code", value=details.get("hs_code", ""))
            cargo_value = st.number_input("Cargo Value (USD)", key="cargo_value", value=details.get("cargo_value", 0))
            customs_info = customs_questions(service, customs=True)

            destination_cost = None
            if incoterm == "FOB":
                destination_cost = st.checkbox("Quote surcharges at destination", key="destination_cost", value=details.get("destination_cost", False))

            details.update({
                "incoterm": incoterm,
                "commodity": commodity,
                "hs_code": hs_code,
                "cargo_value": cargo_value,
                "destination_cost": destination_cost,
                "routes": routes_formatted,
                **customs_info,

            })

    elif role == "Shipper":  # EXPORTATION
        if incoterm in ["FCA", "FAS", "FOB", "CFR", "CIF", "CIP", "CPT"]:
            handle_routes()
            routes = st.session_state.get("routes", [])
            routes_formatted = [
                {"origin": route["origin"], "destination": route["destination"]}
                for route in routes]

            pickup_address = st.text_input("Pickup Address", key="pickup_address", value=details.get("pickup_address", ""))
            zip_code_origin = st.text_input("Zip Code City of Origin", key="zip_code_origin", value=details.get("zip_code_origin", ""))
            commodity = st.text_input("Commodity", key="commodity", value=details.get("commodity", ""))
            hs_code = st.text_input("HS Code", key="hs_code", value=details.get("hs_code", ""))
            customs_info = customs_questions(service, customs=True)

            if incoterm == "CIF":
                insurance = insurance_questions()
                details.update(insurance)

            destination_cost = None
            if incoterm in ["CIF", "CFR"]:
                destination_cost = st.checkbox("Quote surcharges at destination", key="destination_cost", value=details.get("destination_cost", False))
            
            details.update({
                "incoterm": incoterm,
                "pickup_address": pickup_address,
                "zip_code_origin": zip_code_origin,
                "commodity": commodity,
                "hs_code": hs_code,
                "destination_cost": destination_cost,
                "routes": routes_formatted,
                **customs_info,
            })

        elif incoterm in ["DDP", "DAP"]:
            handle_routes()
            routes = st.session_state.get("routes", [])
            routes_formatted = [
                {"origin": route["origin"], "destination": route["destination"]}
                for route in routes]

            pickup_address = st.text_input("Pickup Address", key="pickup_address", value=details.get("pickup_address", ""))
            zip_code_origin = st.text_input("Zip Code City of Origin", key="zip_code_origin", value=details.get("zip_code_origin", ""))
            delivery_address = st.text_input("Delivery Address", key="delivery_address", value=details.get("delivery_address", ""))
            zip_code_destination = st.text_input("Zip Code City of Destination", key="zip_code_destination", value=details.get("zip_code_destination", ""))
            commodity = st.text_input("Commodity", key="commodity", value=details.get("commodity", ""))
            hs_code = st.text_input("HS Code", key="hs_code", value=details.get("hs_code", ""))

            customs_info = None
            if incoterm == "DDP": 
                customs_info = customs_questions(service, customs=True)

                details.update({
                "incoterm": incoterm,
                "pickup_address": pickup_address,
                "zip_code_origin": zip_code_origin,
                "delivery_address": delivery_address,
                "zip_code_destination": zip_code_destination,
                "commodity": commodity,
                "hs_code": hs_code,
                "routes": routes_formatted,
                **customs_info,
            })


            details.update({
                "incoterm": incoterm,
                "pickup_address": pickup_address,
                "zip_code_origin": zip_code_origin,
                "delivery_address": delivery_address,
                "zip_code_destination": zip_code_destination,
                "commodity": commodity,
                "hs_code": hs_code,
                "routes": routes_formatted
            })

    return details, routes

def ground_transport():
    temp_details = st.session_state.get("temp_details", {})
    pickup_address = st.text_input(
            "Pickup Address",
            key="pickup_address",
            value=temp_details.get("pickup_address", "")
        )
    zip_code_origin = st.text_input(
        "Zip Code City of Origin", 
        key="zip_code_origin", 
        value=temp_details.get("zip_code_origin", "")
    )
    delivery_address = st.text_input(
        "Delivery Address",
        key="delivery_address",
        value=temp_details.get("delivery_address", "")
    )
    zip_code_destination = st.text_input(
        "Zip Code City of Destination", 
        key="zip_code_destination", 
        value=temp_details.get("zip_code_destination", "")
        )

    commodity = st.text_input("Commodity", key="commodity", value=temp_details.get("commodity", ""))
    hs_code = st.text_input("HS Code", key="hs_code", value=temp_details.get("hs_code", ""))
    
    temperature, dimensions_info = None, None

    ground_service = st.selectbox(
            "Select Ground Service",
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
            "Temperature °C", key="temperature", value=temp_details.get("temperature", None))
        return {
            "pickup_address": pickup_address,
            "zip_code_origin": zip_code_origin,
            "delivery_address": delivery_address,
            "zip_code_destination": zip_code_destination,
            "commodity": commodity,
            "hs_code": hs_code,
            "ground_service": ground_service,
            "temperature": temperature
        }
    if ground_service == "LTL":
        dimensions_info = dimensions() or {}
        return {
            "pickup_address": pickup_address,
            "zip_code_origin": zip_code_origin,
            "delivery_address": delivery_address,
            "zip_code_destination": zip_code_destination,
            "commodity": commodity,
            "hs_code": hs_code,
            "ground_service": ground_service,
            "temperature": temperature,
            **dimensions_info
        }

    return {
        "pickup_address": pickup_address,
        "zip_code_origin": zip_code_origin,
        "delivery_address": delivery_address,
        "zip_code_destination": zip_code_destination,
        "commodity": commodity,
        "hs_code": hs_code,
        "ground_service": ground_service
    }

def lcl_questions():
    temp_details = st.session_state.get("temp_details", {})
    dimensions_info = None

    dimensions_info = dimensions()

    lcl_description = st.text_area(
        "Weight information for each piece, number of pieces, and dimensions per piece.",
        key="lcl_description",
        value=temp_details.get("lcl_description", "")
    )
    stackable = st.checkbox(
        "Not stackable",
        key="not_stackable",
        value=temp_details.get("not_stackable", False)
    )
    imo_info = imo_questions()

    return {
        **dimensions_info,
        "lcl_description": lcl_description,
        "stackable": stackable,
        **imo_info
    }


def customs_questions(service, customs=False):
    temp_details = st.session_state.get("temp_details", {})
    customs_data = {}
    if not customs:
        country_origin = st.text_input(
                "Country of Origin",
                key="country_origin",
                value=temp_details.get("country_origin", "")
            )
        country_destination = st.text_input(
            "Country of Destination",
            key="country_destination",
            value=temp_details.get("country_destination", "")
        )
        
        commodity = st.text_input("Commodity", key="commodity", value=temp_details.get("commodity", ""))
        hs_code = st.text_input("HS Code", key="hs_code", value=temp_details.get("hs_code", ""))

        dimensions_info = dimensions()
        customs_data.update({
            "country_origin": country_origin,
            "country_destination": country_destination,
            "commodity": commodity,
            "hs_code": hs_code,
            **dimensions_info,
        })

    freight_cost = st.number_input("Freight Cost (USD)", key="freight_cost", value=temp_details.get("freight_cost", 0))
    insurance_cost = st.number_input("Insurance Cost (USD)", key="insurance_cost", value=temp_details.get("insurance_cost", 0))
    cargo_info = cargo(service)
    origin_certificates = st.file_uploader("Certificate of Origin", accept_multiple_files=True, key="origin_certificates")

    origin_certificate_files = []
    if origin_certificates:
        origin_certificate_files = [save_file_locally(file) for file in origin_certificates]
    
    customs_data.update({
        **cargo_info,
        "freight_cost": freight_cost,
        "insurance_cost": insurance_cost,
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

def handle_add_service():
    service = st.session_state["temp_details"]["service"]
    services = load_services()

    if not st.session_state.get("temp_details"):
        st.warning("Please provide the service details before adding.")
        return

    if not service or service == "-- Services --":
        st.warning("Please enter a valid service before proceeding.")
        return

    edit_index = st.session_state.get("edit_index")
    if edit_index is not None:
        if edit_index < len(st.session_state["services"]):
            st.session_state["services"][edit_index] = {
                "service": st.session_state["temp_details"].get("service"),
                "details": st.session_state["temp_details"]
            }
            services[edit_index] = {
                "service": st.session_state["temp_details"].get("service"),
                "details": st.session_state["temp_details"]
            }
            st.success("Service successfully updated.")
            del st.session_state["edit_index"]
        else:
            st.warning("Invalid edit index.")
    else:
        new_service = {
            "service": st.session_state["temp_details"].get("service"),
            "details": st.session_state["temp_details"]
        }
        st.session_state["services"].append(new_service)
        services.append(new_service)
        st.success("Service successfully added.")

    save_services(services)
    st.session_state["temp_details"] = {}
    change_page("requested_services")

def change_page(new_page):
    st.session_state["page"] = new_page

def save_to_google_sheets(dataframe, sheet_name, sheet_id):
    try:
        sheet = client_gcp.open_by_key(sheet_id)
        try:
            worksheet = sheet.worksheet(sheet_name)
            if worksheet.row_count == 0:
                if sheet_name == "Freight":
                    worksheet.append_row(freight_columns)
                elif sheet_name == "Ground Transport":
                    worksheet.append_row(transport_columns)
                elif sheet_name == "Customs":
                    worksheet.append_row(customs_columns)

        except gspread.exceptions.WorksheetNotFound:
            worksheet = sheet.add_worksheet(title=sheet_name, rows="1000", cols="30")
        
            if sheet_name == "Freight":
                worksheet.append_row(freight_columns)
            elif sheet_name == "Ground Transport":
                worksheet.append_row(transport_columns)
            elif sheet_name == "Customs":
                worksheet.append_row(customs_columns)

        if sheet_name == "Freight":
            dataframe = dataframe.reindex(columns=freight_columns)
        elif sheet_name == "Ground Transport":
            dataframe = dataframe.reindex(columns=transport_columns)
        elif sheet_name == "Customs":
            dataframe = dataframe.reindex(columns=customs_columns)

        new_data = dataframe.fillna("").values.tolist()

        worksheet.append_rows(new_data, table_range="A2")

    except Exception as e:
        st.error(f"Failed to save data to Google Sheets: {e}")

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
    try:
        sheet = client_gcp.open_by_key(time_sheet_id)

        worksheet_list = [ws.title for ws in sheet.worksheets()]
        if sheet_name not in worksheet_list:
            return set()
    
        worksheet = sheet.worksheet(sheet_name)
        existing_ids = worksheet.col_values(1)
        return set(existing_ids[1:]) 

    except gspread.exceptions.SpreadsheetNotFound:
        st.error("No se encontró la hoja de cálculo con el ID proporcionado.")
        return set()

    except gspread.exceptions.WorksheetNotFound:
        st.error(f"No se encontró la pestaña '{sheet_name}' en la hoja de cálculo.")
        return set()

    except Exception as e:
        st.error(f"Error al cargar IDs desde Google Sheets: {e}")
        return set()

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