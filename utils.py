import streamlit as st
from google.oauth2.service_account import Credentials
import gspread
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import os


freight_columns = [
    "commercial", "service", "client", "incoterm", "transport_type", "modality", "origin", "zip_code_origin", "destination", "zip_code_destination", "commodity", "type_container",
    "reinforced", "suitable_food", "imo_cargo", "un_code", "msds", "fruit", "type_fruit", "positioning", "pickup_city",
    "lcl_fcl_mode", "fcl_lcl_mode",  "reefer_cont_type", "pickup_thermo_king", "pickup_address", "drayage_reefer", "drayage_address",
    "delivery_address", "destination_costs", "value", "commercial_invoice_link",
    "packing_list_link", "weight", 
]

transport_columns = [
    "commercial", "service", "client", "incoterm", "transport_type", "modality", "origin", "zip_code_origin", "destination", "zip_code_destination", "commodity", 
    "ground_service", "thermo_type",  "weigth_lcl", "volume", "length", "width", "depth", "lcl_description", "stackable", 
    "imo_cargo", "un_code", "msds", "commercial_invoice_link", "packing_list_link", "pickup_address", "delivery_address",
    "destination_costs", "value"
]

customs_columns = [
    "commercial", "service", "client", "incoterm", "transport_type", "modality", "origin", "zip_code_origin", "destination", "zip_code_destination", "commodity",
    "commercial_invoice_link", "packing_list_link", "weight", "volume", "length", "width", "depth", "cargo_value", "hs_code", "technical_sheet"
]


sheet_id = st.secrets["general"]["sheet_id"]
DRIVE_ID = st.secrets["general"]["drive_id"]
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
            st.success(f"Folder created for this request")

    return folder_id


def route():
    origin = st.text_input("Port of Origin/ Pick up Address/ Country of Origin", key="origen")
    zip_code_origin = st.text_input("Zip Code (optional)", key="codigo_postal_origen")
    destination = st.text_input("Port of Destination/ Delivery Address/ Country of Destination", key="destino")
    zip_code_destination = st.text_input("Zip Code (optional)", key="codigo_postal_destino")
    commodity = st.text_input("Commodity", key="commodity")
    return{
        "origin": origin,
        "zip_code_origin": zip_code_origin,
        "destination": destination,
        "zip_code_destination": zip_code_destination,
        "commodity": commodity
    }

def cargo(folder_id):
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
    weight_lcl = st.number_input("Cargo weight (KG)")
    volume = st.number_input("Pallet volume")
    length = st.number_input("Pallet length (CM)")
    width = st.number_input("Pallet width (CM)")
    depth = st.number_input("Pallet depth (CM)")

    return{
        "weigth_lcl": weight_lcl,
        "volume": volume,
        "length": length,
        "width": width,
        "depth": depth,
    }


def common_questions(folder_id):
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
        key="type_container"
    )
    reinforced = st.checkbox("Should it be reinforced?", key="reforzado")
    suitable_food = st.checkbox("Suitable for foodstuffs?", key="apto_alimentos")

    p_imo = imo_questions(folder_id)
    fruit = st.checkbox("Is it fruit?", key="fruit")
    type_fruit = None
    if fruit:
        type_fruit = st.text_input("Specify fruit type", key="type_fruit")

    positioning = st.radio(
    "Container Positioning",
    ["In yard", "At port", "Not Applicable"],
    key="positioning"
    )
    pickup_city = None
    if positioning == "In yard":
        pickup_city = st.text_input("Pickup City", key="pickup_city")

    lcl_fcl_mode = st.checkbox("Is it LCL-FCL mode?", key="lcl_fcl_mode")

    fcl_lcl_mode = st.checkbox("Is it FCL-LCL mode?", key="fcl_lcl_mode")

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
    cargo_value = st.number_input("Cargo Value (USD)")
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
    imo_cargo = st.checkbox("Is it considered IMO?", key="imo_cargo")
    un_code, msds, msds_link = None, None, None

    if imo_cargo:
        un_code = st.text_input("UN Code", key="un_code")
        msds = st.file_uploader("Attach MSDS", key="msds")

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

def questions_by_incoterm(incoterm, details, folder_id):
    if incoterm == "EXW":
        pickup_address = st.text_input("Pickup Address")
        details["pickup_address"] = pickup_address

    elif incoterm == "FCA":
        origin_customs_payer = st.radio("Origin Customs Payer", ["Shipper", "Consignee"])
        details["origin_customs_payer"] = origin_customs_payer

    elif incoterm in ["CIF", "CFR"]:
        destination_costs = st.radio("Do you require destination cost quotation?", ["Yes", "No"])
        insurance = insurance_questions(folder_id) 
        details.update(insurance) 
        details["destination_costs"] = destination_costs

    elif incoterm in ["DDP", "DAP"]:
        cargo_details = cargo(folder_id)
        pickup_address = st.text_input("Pickup Address")
        delivery_address = st.text_input("Delivery Address")
        destination_costs = st.radio("Do you require destination cost quotation?", ["Yes", "No"])
        value = st.number_input("Enter the cargo value")

        details.update({
            "incoterm": incoterm,
            **cargo_details,
            "pickup_address": pickup_address,
            "delivery_address": delivery_address,
            "destination_costs": destination_costs,
            "value": value
        })

    return details


def lcl_questions(folder_id, service):
    route_info = route()
    ground_service, thermo_type = None, None
    if service == "Ground Transportation":
        ground_service = st.selectbox(
                    "Select Ground Service",
                    ["Drayage 20 STD", "Drayage 40 STD/40HQ", "FTL 53 FT", "Flat Bed", "Box Truck",
                    "Drayage Reefer 20 STD", "Drayage Reefer 40 STD", "Mula Carpa", "Thermo King", "LTL"],
                    key="ground_service"
        )
        if ground_service == "Thermo King":
            thermo_type = st.radio("Specify the type", ["Refrigerated", "Frozen"], key="thermo_type")
        st.markdown("**Note: if LTL please enter the following information, otherwise continue.**")
        dimensions_info = dimensions()
    else:
        dimensions_info = dimensions()

    lcl_description = st.text_area("Weight information for each piece, number of pieces, and dimensions per piece.")
    stackable = st.checkbox("Are the pieces stackable?")
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

def customs_questions(folder_id):
    route_info = route()
    cargo_info = cargo(folder_id)
    dimensions_info = dimensions()
    insurance_info = insurance_questions(folder_id)

    return {
        **route_info,
        **cargo_info,
        **dimensions_info,
        **insurance_info
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
        return folder.get('id')
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
        
        return folder.get('id')
    except Exception as e:
        st.error(f"Failed to create folder: {e}")
        return None


