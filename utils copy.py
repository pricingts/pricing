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

freight_columns = [
    "request_id", "time", "commercial", "service", "client", "client_role", "incoterm", "transport_type", "modality", "routes_info", "pickup_address", "zip_code_origin", "delivery_address", "zip_code_destination", 
    "commodity", "hs_code", "cargo_value", "freight_cost", "insurance_cost", "origin_certificates", "commercial_invoice_links", "packing_list_links", "technical_sheets_links", "weight", "destination_cost", 
    "type_container", "reinforced", "suitable_food", "imo_cargo", "un_code", "msds", "positioning", "pickup_city", "lcl_fcl_mode", "drayage_reefer", "reefer_cont_type", "pickup_thermo_king",
    "number_pallets_input", "info_pallets_str", "pallets_links", "lcl_description", "not_stackable",
    "final_comments", "additional_documents_links"
]

transport_columns = [
    "request_id", "time", "commercial", "service", "client", "pickup_address", "zip_code_origin", "delivery_address", "zip_code_destination", "commodity", "hs_code",
    "ground_service", "temperature",
    "number_pallets_input", "info_pallets_str", "pallets_links", "lcl_description", "not_stackable",
    "final_comments", "additional_documents_links"
]

customs_columns = [
    "request_id", "time", "commercial", "service", "client", "incoterm", "country_origin", "country_destination", "commodity", "hs_code", "freight_cost", 
    "number_pallets", "info_pallets_str", "info_pallets_link",
    "insurance_cost", "origin_certificate_links", "commercial_invoice_links", "packing_list_links",
    "final_comments", "additional_documents_links"
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
            st.success(f"Folder created for this request")

    return folder_id, folder_link

def cargo(folder_id, service):
    weight = None

    commercial_invoices = st.file_uploader("Attach Commercial Invoices", accept_multiple_files=True, key="commercial_invoices")
    packing_lists = st.file_uploader("Attach Packing Lists", accept_multiple_files=True, key="packing_lists")

    ci_links = []
    if commercial_invoices:
        for commercial_invoice in commercial_invoices:
            if commercial_invoice.name not in st.session_state["uploaded_files"]:
                _, commercial_invoice_link = upload_file_to_folder(commercial_invoice, folder_id)
                if commercial_invoice_link:
                    st.session_state["uploaded_files"][commercial_invoice.name] = commercial_invoice_link
                    ci_links.append(commercial_invoice_link)
                    st.success(f"Commercial Invoice '{commercial_invoice.name}' uploaded successfully: [View File]({commercial_invoice_link})")

    pl_links = []
    if packing_lists:
        for packing_list in packing_lists:
            if packing_list.name not in st.session_state["uploaded_files"]:
                _, packing_list_link = upload_file_to_folder(packing_list, folder_id)
                if packing_list_link:
                    st.session_state["uploaded_files"][packing_list.name] = packing_list_link
                    pl_links.append(packing_list_link)
                    st.success(f"Packing List '{packing_list.name}' uploaded successfully: [View File]({packing_list_link})")

    if service != "Customs Brokerage":
        weight = st.number_input("Weight", key="weight")

    return {
        "commercial_invoice_links": ci_links,
        "packing_list_links": pl_links,
        "weight": weight
    }

def dimensions(folder_id):
    temp_details = st.session_state.get("temp_details", {})

    if "number_pallets" not in st.session_state:
        st.session_state.number_pallets = temp_details.get("number_pallets", 1)

    number_pallets = st.number_input(
        "Number of pallets",
        key="number_pallets_input",
        value=int(st.session_state.number_pallets),
        step=1,
        min_value=1
    )

    if number_pallets != st.session_state.number_pallets:
        st.session_state.number_pallets = number_pallets
    
    info_pallets = []

    if st.session_state.number_pallets <= 7: 

        for i in range(1, st.session_state.number_pallets + 1):  
            st.markdown(f"### Pallet {i} Details") 
            weight_lcl = st.number_input(
                f"Pallet {i} weight (KG)", 
                key=f"weight_lcl_{i}", 
                value=temp_details.get(f"weight_lcl_{i}", 0), 
                step=1,
                min_value=0
            )
            volume = st.number_input(
                f"Pallet {i} volume (CBM)", 
                key=f"volume_{i}", 
                value=temp_details.get(f"volume_{i}", 0.0), 
                step=0.01,
                min_value=0.0
            )
            length = st.number_input(
                f"Pallet {i} length (CM)", 
                key=f"length_{i}", 
                value=temp_details.get(f"length_{i}", 0), 
                step=1,
                min_value=0
            )
            width = st.number_input(
                f"Pallet {i} width (CM)", 
                key=f"width_{i}", 
                value=temp_details.get(f"width_{i}", 0), 
                step=1,
                min_value=0
            )
            height = st.number_input(
                f"Pallet {i} height (CM)", 
                key=f"height_{i}", 
                value=temp_details.get(f"height_{i}", 0), 
                step=1,
                min_value=0
            )

            if volume == 0 and length > 0 and width > 0 and height > 0:
                volume = (length * width * height) 
                st.write(f"Calculated Volume for Pallet {i}: {volume:.2f} CBM")

            info_pallets.append({
                "weight_lcl": weight_lcl,
                "volume": volume,
                "length": length,
                "width": width,
                "height": height
            })

        return {
            "number_pallets": st.session_state.number_pallets,
            "info_pallets": info_pallets
        }

    else:
        info_pallets_files = st.file_uploader("Attach Pallets Information", accept_multiple_files=True,  # Permite cargar múltiples archivos
        key="info_pallets_files")

        pallets_links = []
        if info_pallets_files:
            for info_pallet in info_pallets_files:
                if info_pallet.name not in st.session_state["uploaded_files"]:
                    _, info_pallet_link = upload_file_to_folder(info_pallet, folder_id)
                    if info_pallet_link:
                        st.session_state["uploaded_files"][info_pallet.name] = info_pallet_link
                        pallets_links.append(info_pallet_link)
                        st.success(f"Pallet information '{info_pallet.name}' uploaded successfully: [View File]({info_pallet_link})")

        return {
            "number_pallets": st.session_state.number_pallets,
            "pallets_links": pallets_links
        }

def add_route():
    st.session_state["routes"].append({"origin": "", "destination": ""})

def common_questions(folder_id):
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

    p_imo = imo_questions(folder_id)

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

def insurance_questions(folder_id):
    technical_sheets = st.file_uploader("Attach technical sheets", accept_multiple_files=True, key="technical_sheets")

    ts_links = []
    if technical_sheets:
        for technical_sheet in technical_sheets:
            if technical_sheet.name not in st.session_state["uploaded_files"]:
                _, technical_sheet_link = upload_file_to_folder(technical_sheet, folder_id)
                if technical_sheet_link:
                    st.success(f"Technical Sheet '{technical_sheet.name}' uploaded successfully: [View File]({technical_sheet_link})")
                    st.session_state["uploaded_files"][technical_sheet.name] = technical_sheet_link
                    ts_links.append(technical_sheet_link)

    return {
        "technical_sheets_links": ts_links
    }

def imo_questions(folder_id):
    temp_details = st.session_state.get("temp_details", {})
    imo_cargo = st.checkbox(
        "IMO", 
        key="imo_cargo", 
        value=temp_details.get("imo_cargo", False)
    )
    un_code, msds, msds_link = None, None, None

    if imo_cargo:
        un_code = st.text_input(
            "UN Code", 
            key="un_code", 
            value=temp_details.get("un_code", "")
        )
        msds = st.file_uploader(
            "Attach MSDS", 
            key="msds"
        )

        if msds:
            if msds.name not in st.session_state["uploaded_files"]:
                _, msds_link = upload_file_to_folder(msds, folder_id)
                if msds_link:
                    st.success(f"MSDS uploaded successfully: [View File]({msds_link})")
                    st.session_state["uploaded_files"][msds.name] = msds_link

    return {
        "imo_cargo": imo_cargo,
        "un_code": un_code,
        "msds": msds_link
    }

def initialize_routes():
    if "routes" not in st.session_state:
        st.session_state["routes"] = [{"origin": "", "destination": ""}]

def add_route():
    st.session_state["routes"].append({"origin": "", "destination": ""})

def handle_routes():
    initialize_routes()
    for i, route in enumerate(st.session_state["routes"]):
        st.write(f"Route {i + 1}")
        cols = st.columns(2)
        with cols[0]:
            route["origin"] = st.text_input(
                f"Port of Origin {i + 1}", key=f"origin_{i}", value=route["origin"]
            )
        with cols[1]:
            route["destination"] = st.text_input(
                f"Port of Destination {i + 1}", key=f"destination_{i}", value=route["destination"]
            )
    if st.button("Add other route"):
        add_route()

def questions_by_incoterm(incoterm, details, folder_id, service, role):
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
            customs_info = customs_questions(folder_id, service, customs=True)

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
            customs_info = customs_questions(folder_id, service, customs=True)

            if incoterm == "CIF":
                insurance = insurance_questions(folder_id)
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
                customs_info = customs_questions(folder_id, service, customs=True)

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

def ground_transport(folder_id):
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
        dimensions_info = dimensions(folder_id) or {}
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

def lcl_questions(folder_id):
    temp_details = st.session_state.get("temp_details", {})
    dimensions_info = None

    dimensions_info = dimensions(folder_id)

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
    imo_info = imo_questions(folder_id)

    return {
        **dimensions_info,
        "lcl_description": lcl_description,
        "stackable": stackable,
        **imo_info
    }


def customs_questions(folder_id, service, customs=False):
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

        dimensions_info = dimensions(folder_id)
        customs_data.update({
            "country_origin": country_origin,
            "country_destination": country_destination,
            "commodity": commodity,
            "hs_code": hs_code,
            **dimensions_info,
        })

    freight_cost = st.number_input("Freight Cost (USD)", key="freight_cost", value=temp_details.get("freight_cost", 0))
    insurance_cost = st.number_input("Insurance Cost (USD)", key="insurance_cost", value=temp_details.get("insurance_cost", 0))
    cargo_info = cargo(folder_id, service)
    origin_certificates = st.file_uploader("Certificate of Origin", accept_multiple_files=True, key="origin_certificates")

    origin_certificate_links = []
    if origin_certificates:
        for origin_certificate in origin_certificates:
            if hasattr(origin_certificate, "name") and origin_certificate.name not in st.session_state.get("uploaded_files", {}):
                _, origin_certificate_link = upload_file_to_folder(origin_certificate, folder_id)
                if origin_certificate_link:
                    st.session_state.setdefault("uploaded_files", {})[origin_certificate.name] = origin_certificate_link
                    origin_certificate_links.append(origin_certificate_link)
                    st.success(f"Origin Certificate '{origin_certificate.name}' uploaded successfully: [View File]({origin_certificate_link})")

    customs_data.update({
        **cargo_info,
        "freight_cost": freight_cost,
        "insurance_cost": insurance_cost,
        "origin_certificate_links": origin_certificate_links,
    })

    return customs_data

def final_questions(folder_id):
    temp_details = st.session_state.get("temp_details", {})

    final_comments = st.text_area("Final Comments", key="final_comments", value=temp_details.get("final_comments", ""))
    st.session_state["temp_details"]["final_comments"] = final_comments

    additional_documents = st.file_uploader("Attach Additional Documents", accept_multiple_files=True, key="additional_documents")

    uploaded_links = []
    if additional_documents:
        for document in additional_documents:
            if document.name not in st.session_state["uploaded_files"]:
                _, document_link = upload_file_to_folder(document, folder_id)
                if document_link:
                    st.session_state["uploaded_files"][document.name] = document_link
                    uploaded_links.append(document_link)
                    st.success(f"Document '{document.name}' uploaded successfully: [View File]({document_link})")

    return {
        "final_comments": final_comments,
        "additional_documents_links": uploaded_links
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

def upload_file_to_folder(file, folder_id):
    try:
        temp_dir = "temp"
        if not os.path.exists(temp_dir):
            os.makedirs(temp_dir)

        temp_file_path = os.path.join(temp_dir, file.name)
        
        with open(temp_file_path, "wb") as temp_file:
            temp_file.write(file.read())
        
        file_metadata = {
            'name': file.name,
            'parents': [folder_id]
        }
        media = MediaFileUpload(temp_file_path, resumable=True)

        uploaded_file = drive_service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id, webViewLink',
            supportsAllDrives=True  
        ).execute()

        os.remove(temp_file_path)
        
        return uploaded_file.get('id'), uploaded_file.get('webViewLink')
    except Exception as e:
        st.error(f"Failed to upload file: {e}")
        return None, None

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


SERVICES_FILE = "services.json"

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