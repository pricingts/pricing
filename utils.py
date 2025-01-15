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
    "request_id", "time", "commercial", "service", "client", "incoterm", "transport_type", "modality", "origin", "zip_code_origin", "destination", "zip_code_destination", "commodity", "type_container",
    "reinforced", "suitable_food", "imo_cargo", "un_code", "msds", "fruit", "type_fruit", "positioning", "pickup_city", 
    "ground_service", "thermo_type", "weigth_lcl", "volume", "length", "width", "depth", "lcl_description", "stackable",
    "lcl_fcl_mode", "fcl_lcl_mode",  "reefer_cont_type", "pickup_thermo_king", "pickup_address", "drayage_reefer", "drayage_address",
    "delivery_address", "destination_costs", "cargo_value", "commercial_invoice_link",
    "packing_list_link", "weight", "final_comments"
]

transport_columns = [
    "request_id", "time", "commercial", "service", "client", "incoterm", "transport_type", "modality", "origin", "zip_code_origin", "destination", "zip_code_destination", "commodity", 
    "ground_service", "thermo_type",  "weigth_lcl", "volume", "length", "width", "depth", "lcl_description", "stackable", 
    "imo_cargo", "un_code", "msds", "commercial_invoice_link", "packing_list_link", "pickup_address", "delivery_address",
    "destination_costs", "cargo_value", "final_comments"
]

customs_columns = [
    "request_id", "time", "commercial", "service", "client", "incoterm", "transport_type", "modality", "origin", "zip_code_origin", "destination", "zip_code_destination", "commodity",
    "commercial_invoice_link", "packing_list_link", "weight", "volume", "length", "width", "depth", "cargo_value", "hs_code", "technical_sheet", "freight_cost", "insurance_cost", "origin_certificate", "final_comments"
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

@st.cache_data(ttl=3600, show_spinner=False)
def process_route_data(origin, zip_code_origin, destination, zip_code_destination, commodity):
    return {
        "origin": origin,
        "zip_code_origin": zip_code_origin,
        "destination": destination,
        "zip_code_destination": zip_code_destination,
        "commodity": commodity
    }

def route():
    temp_details = st.session_state.get("temp_details", {})
    origin = st.text_input("Port of Origin/ Pick up Address/ Country of Origin", key="origin", value=temp_details.get("origin", None))
    zip_code_origin = st.text_input("Zip Code (optional)", key="zip_code_origin", value=temp_details.get("zip_code_origin", None))
    destination = st.text_input("Port of Destination/ Delivery Address/ Country of Destination", key="destination", value=temp_details.get("destination", None))
    zip_code_destination = st.text_input("Zip Code (optional)", key="zip_code_destination", value=temp_details.get("zip_code_destination", None))
    commodity = st.text_input("Commodity", key="commodity", value=temp_details.get("commodity", None))
    route_data = process_route_data(origin, zip_code_origin, destination, zip_code_destination, commodity)

    return route_data

def cargo(folder_id, service):
    weight = None
    if service == "Customs Brokerage":
        commercial_invoice = st.file_uploader("Attach Commercial Invoice")
        packing_list = st.file_uploader("Attach Packing List")

        commercial_invoice_link = None
        packing_list_link = None

        if commercial_invoice:

            if commercial_invoice.name not in st.session_state["uploaded_files"]:
                _, commercial_invoice_link = upload_file_to_folder(commercial_invoice, folder_id)
                if commercial_invoice_link:
                    st.session_state["uploaded_files"][commercial_invoice.name] = commercial_invoice_link
                    st.success(f"Commercial Invoice uploaded successfully: [View File]({commercial_invoice_link})")
            else:
                commercial_invoice_link = st.session_state["uploaded_files"][commercial_invoice.name]

        if packing_list:

            if packing_list.name not in st.session_state["uploaded_files"]:
                _, packing_list_link = upload_file_to_folder(packing_list, folder_id)
                if packing_list_link:
                    st.session_state["uploaded_files"][packing_list.name] = packing_list_link
                    st.success(f"Packing List uploaded successfully: [View File]({packing_list_link})")
            else: 
                packing_list_link = st.session_state["uploaded_files"][packing_list.name]

        return {
            "commercial_invoice_link": commercial_invoice_link,
            "packing_list_link": packing_list_link,
            "weight": weight
        }
    
    else: 
        commercial_invoice = st.file_uploader("Attach Commercial Invoice")
        packing_list = st.file_uploader("Attach Packing List")
        weight = st.number_input("Weight")

        commercial_invoice_link = None
        packing_list_link = None

        if commercial_invoice:

            if commercial_invoice.name not in st.session_state["uploaded_files"]:
                _, commercial_invoice_link = upload_file_to_folder(commercial_invoice, folder_id)
                if commercial_invoice_link:
                    st.session_state["uploaded_files"][commercial_invoice.name] = commercial_invoice_link
                    st.success(f"Commercial Invoice uploaded successfully: [View File]({commercial_invoice_link})")
            else:
                commercial_invoice_link = st.session_state["uploaded_files"][commercial_invoice.name]

        if packing_list:

            if packing_list.name not in st.session_state["uploaded_files"]:
                _, packing_list_link = upload_file_to_folder(packing_list, folder_id)
                if packing_list_link:
                    st.session_state["uploaded_files"][packing_list.name] = packing_list_link
                    st.success(f"Packing List uploaded successfully: [View File]({packing_list_link})")
            else: 
                packing_list_link = st.session_state["uploaded_files"][packing_list.name]

        return {
            "commercial_invoice_link": commercial_invoice_link,
            "packing_list_link": packing_list_link,
            "weight": weight
            }

def dimensions():
    temp_details = st.session_state.get("temp_details", {})

    weight_lcl = st.number_input("Cargo weight (KG)", key="weight_lcl", value=temp_details.get("weight_lcl", None))
    volume = st.number_input("Pallet volume", key="volume", value=temp_details.get("volume", None))
    length = st.number_input("Pallet length (CM)", key="length", value=temp_details.get("volume", None))
    width = st.number_input("Pallet width (CM)", key="width", value=temp_details.get("width", None))
    depth = st.number_input("Pallet depth (CM)", key="depth", value=temp_details.get("depth", None))

    return{
        "weigth_lcl": weight_lcl,
        "volume": volume,
        "length": length,
        "width": width,
        "depth": depth,
    }

def common_questions(folder_id):

    temp_details = st.session_state.get("temp_details", {})

    p_ruta = route()
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
    reinforced = st.checkbox("Should it be reinforced?", key="reinforced", value=temp_details.get("reinforced", False))
    suitable_food = st.checkbox("Suitable for foodstuffs?", key="suitable_food", value=temp_details.get("suitable_food", False))

    p_imo = imo_questions(folder_id)
    fruit = st.checkbox("Is it fruit?", key="fruit", value=temp_details.get("fruit", False))
    type_fruit = None
    if fruit:
        type_fruit = st.text_input("Specify fruit type", key="type_fruit", value=temp_details.get("type_fruit", False))

    positioning = st.radio(
        "Container Positioning",
        ["In yard", "At port", "Not Applicable"],
    key="positioning", index=["In yard", "At port", "Not Applicable"].index(temp_details.get("positioning", "In yard"))
    )

    pickup_city = temp_details.get("pickup_city", "")

    if positioning == "In yard":
        pickup_city = st.text_input("Pickup City", key="pickup_city", value=pickup_city)

    lcl_fcl_mode = st.checkbox("Is it LCL-FCL mode?", key="lcl_fcl_mode", value=temp_details.get("lcl_fcl_mode", False))

    fcl_lcl_mode = st.checkbox("Is it FCL-LCL mode?", key="fcl_lcl_mode", value=temp_details.get("fcl_lcl_mode", False))

    return {
        **p_ruta,
        "type_container": type_container,
        "reinforced": reinforced,
        "suitable_food": suitable_food,
        **p_imo,
        "fruit": fruit,
        "type_fruit": type_fruit,
        "positioning": positioning,
        "pickup_city": pickup_city,
        "lcl_fcl_mode": lcl_fcl_mode,
        "fcl_lcl_mode": fcl_lcl_mode,
    }

def handle_refrigerated_cargo(cont_type):
    reefer_cont_type = None
    if cont_type == "Reefer 40'":
        reefer_cont_type = st.radio("Specify the type", ["Controlled Atmosphere", "Cold Treatment"], key="reefer_type")

    pickup_thermo_king = st.radio("Thermo King Pick up?", ["Yes", "No"], key="pickup_thermo_king")
    pickup_address, drayage_address = None, None

    if pickup_thermo_king == "Yes":
        pickup_address = st.text_input("Pick up Adress", key="pickup_address")
    drayage_reefer = st.radio("Drayage Reefer?", ["Yes", "No"], key="pickup_drayage_reefer")
    if drayage_reefer == "Yes":
        drayage_address = st.text_input("Drayage Address", key="drayage_address")

    return {
        "reefer_cont_type": reefer_cont_type,
        "pickup_thermo_king": pickup_thermo_king,
        "pickup_address": pickup_address,
        "drayage_reefer": drayage_reefer,
        "drayage_address": drayage_address,
    }

def insurance_questions(folder_id):
    cargo_value = st.number_input("Cargo Value (USD)", value=None)
    hs_code = st.text_input("HS Code")
    technical_sheet = st.file_uploader("Attach technical sheet")

    technical_sheet_link = None

    if technical_sheet:

        if technical_sheet.name not in st.session_state["uploaded_files"]:
            _, technical_sheet_link = upload_file_to_folder(technical_sheet, folder_id)
            if technical_sheet_link:
                st.success(f"Technical Sheet uploaded successfully: [View File]({technical_sheet_link})")
                st.session_state["uploaded_files"][technical_sheet.name] = technical_sheet_link

    return {
        "cargo_value": cargo_value,
        "hs_code": hs_code,
        "technical_sheet": technical_sheet_link
    }

def imo_questions(folder_id):
    temp_details = st.session_state.get("temp_details", {})
    imo_cargo = st.checkbox(
        "Is it considered IMO?", 
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

def questions_by_incoterm(incoterm, details, folder_id, service):
    if incoterm == "EXW":
        pickup_address = st.text_input(
            "Pickup Address",
            key="pickup_address",
            value=details.get("pickup_address", "")
        )
        details["pickup_address"] = pickup_address

    elif incoterm == "FCA":
        origin_customs_payer = st.radio(
            "Origin Customs Payer",
            ["Shipper", "Consignee"],
            key="origin_customs_payer",
            index=["Shipper", "Consignee"].index(details.get("origin_customs_payer", "Shipper"))
        )
        details["origin_customs_payer"] = origin_customs_payer

    elif incoterm in ["CIF", "CFR"]:
        destination_costs = st.radio(
            "Do you require destination cost quotation?",
            ["Yes", "No"],
            key="destination_costs",
            index=["Yes", "No"].index(details.get("destination_costs", "No"))
        )
        insurance = insurance_questions(folder_id)
        details.update(insurance)
        details["destination_costs"] = destination_costs

    elif incoterm in ["DDP", "DAP"]:
        cargo_details = cargo(folder_id, service)
        pickup_address = st.text_input(
            "Pickup Address",
            key="pickup_address",
            value=details.get("pickup_address", "")
        )
        delivery_address = st.text_input(
            "Delivery Address",
            key="delivery_address",
            value=details.get("delivery_address", "")
        )
        destination_costs = st.radio(
            "Do you require destination cost quotation?",
            ["Yes", "No"],
            key="destination_costs",
            index=["Yes", "No"].index(details.get("destination_costs", "No"))
        )
        cargo_value = st.number_input(
            "Cargo Value (USD)",
            value=details.get("cargo_value", 0)
        )

        details.update({
            "incoterm": incoterm,
            **cargo_details,
            "pickup_address": pickup_address,
            "delivery_address": delivery_address,
            "destination_costs": destination_costs,
            "cargo_value": cargo_value
        })

    return details


def lcl_questions(folder_id, service):
    temp_details = st.session_state.get("temp_details", {})
    route_info = route()
    ground_service, thermo_type = None, None
    if service == "Ground Transportation":
        ground_service = st.selectbox(
            "Select Ground Service",
            [
                "Drayage 20 STD", "Drayage 40 STD/40HQ", "FTL 53 FT", "Flat Bed", "Box Truck",
                "Drayage Reefer 20 STD", "Drayage Reefer 40 STD", "Mula Carpa", "Thermo King", "LTL"
            ],
            key="ground_service",
            index=[
                "Drayage 20 STD", "Drayage 40 STD/40HQ", "FTL 53 FT", "Flat Bed", "Box Truck",
                "Drayage Reefer 20 STD", "Drayage Reefer 40 STD", "Mula Carpa", "Thermo King", "LTL"
            ].index(temp_details.get("ground_service", "Drayage 20 STD"))
        )
        if ground_service == "Thermo King":
            thermo_type = st.radio(
                "Specify the type",
                ["Refrigerated", "Frozen"],
                key="thermo_type",
                index=["Refrigerated", "Frozen"].index(temp_details.get("thermo_type", "Refrigerated"))
            )
        st.markdown("**Note: if LTL please enter the following information, otherwise continue.**")
        dimensions_info = dimensions()
    else:
        dimensions_info = dimensions()

    lcl_description = st.text_area(
        "Weight information for each piece, number of pieces, and dimensions per piece.",
        key="lcl_description",
        value=temp_details.get("lcl_description", "")
    )
    stackable = st.checkbox(
        "Are the pieces stackable?",
        key="stackable",
        value=temp_details.get("stackable", False)
    )
    imo_info = imo_questions(folder_id)

    return {
        **route_info,
        "ground_service": ground_service,
        "thermo_type": thermo_type,
        **dimensions_info,
        "lcl_description": lcl_description,
        "stackable": stackable,
        **imo_info
    }

def customs_questions(folder_id, service):
    temp_details = st.session_state.get("temp_details", {})

    route_info = route()
    dimensions_info = dimensions()
    freight_cost = st.number_input("Freight Cost (USD)", key="freight_cost", value=temp_details.get("freight_cost", None))
    insurance_cost = st.number_input("Insurance Cost (USD)", key="insurance_cost", value=temp_details.get("insurance_cost", None))
    insurance_info = insurance_questions(folder_id)
    cargo_info = cargo(folder_id, service)
    origin_certificate = st.file_uploader("Certificate of Origin", key="origin_certificate")

    origin_certificate_link= None

    if origin_certificate:
        if origin_certificate.name not in st.session_state["uploaded_files"]:
            _, origin_certificate_link = upload_file_to_folder(origin_certificate, folder_id)
            if origin_certificate_link:
                st.session_state["uploaded_files"][origin_certificate.name] = origin_certificate_link
                st.success(f"Origin Certificate uploaded successfully: [View File]({origin_certificate_link})")
        else:
            origin_certificate_link = st.session_state["uploaded_files"][origin_certificate.name]

    return {
        **route_info,
        **cargo_info,
        **dimensions_info,
        **insurance_info,
        "freight_cost": freight_cost,
        "insurance_cost": insurance_cost,
        "origin_certificate": origin_certificate_link
    }

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
            worksheet = sheet.add_worksheet(title=sheet_name, rows="1000", cols="20")
        
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


def create_folder(folder_name, parent_folder_id):
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
        folder_link = f"https://drive.google.com/drive/folders/{folder_id}"

        return folder_id, folder_link
    
    except Exception as e:
        st.error(f"Failed to create folder: {e}")
        return None
    

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

def log_time(start_time, end_time, duration):
    sheet_name = "Timestamp"
    try:
        sheet = client_gcp.open_by_key(time_sheet_id)
        try:
            worksheet = sheet.worksheet(sheet_name)
            start_time_str = start_time.strftime('%Y-%m-%d %H:%M:%S')
            end_time_str = end_time.strftime('%Y-%m-%d %H:%M:%S')
            worksheet.append_row([start_time_str, end_time_str, duration])
        
        except gspread.exceptions.WorksheetNotFound:
            worksheet = sheet.add_worksheet(title=sheet_name, rows="1000", cols="20")
            worksheet.append_row(["Start Time", "End Time", "Duration (seconds)"])
            start_time_str = start_time.strftime('%Y-%m-%d %H:%M:%S')
            end_time_str = end_time.strftime('%Y-%m-%d %H:%M:%S')
            worksheet.append_row([start_time_str, end_time_str, duration])

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