import os
import shutil
from typing import TypedDict, Literal
import json
import math
import time
import dpath
from luau.convert import mark_as_literal, from_dict
import requests
from PIL import Image, ImageOps

PNG_PATH = "png"
OUT_DIR = "out"
OUT_IMG_DIR = f"{OUT_DIR}/asset"
OUT_MAP_DIR = f"{OUT_DIR}/map"
ASSET_ID_PATH = f"{OUT_DIR}/asset_ids.json"
DECAL_ID_PATH = f"{OUT_DIR}/decal_ids.json"
DECAL_SCRIPT_PATH = f"{OUT_DIR}/convert.luau"
DECAL_PLACE_PATH = f"{OUT_DIR}/decal-loader.rbxl"
LUAU_OUT_DIR = f"src"
AUTH_KEY: str
with open("scripts/auth.txt", "r") as auth_file:
	AUTH_KEY = auth_file.read()

Size = Literal[18, 24, 36, 48]
Style = Literal["Default", "Outlined", "Round", "Sharp", "TwoTone"]
Scale = Literal[1, 2, 3, 4]
STYLE_PREFIX = "materialicons"
MAX_DIM = 1008#1008 #actually 1024 but this is divisible by the sizes

DIR_TO_STYLE: dict[str, Style] = {
	f"{STYLE_PREFIX}": "Default",
	f"{STYLE_PREFIX}outlined": "Outlined",
	f"{STYLE_PREFIX}round": "Round",
	f"{STYLE_PREFIX}sharp": "Sharp",
	f"{STYLE_PREFIX}twotone": "TwoTone",
}

DP_TO_SIZE: dict[str, Size] = {
	"18dp": 18,
	"24dp": 24,
	"36dp": 36,
	"48dp": 48,
}

SCALE_TO_SCALE: dict[str, Scale] = {
	"1x": 1,
	"2x": 2,
	"3x": 3,
	"4x": 4,
}

BAD_ICONS: list[str] = [
	"smoke_free",
	"smoking_rooms",
	"vaping_rooms",
	"vape_free",
	"local_bar",
	"liquor",
	"wine_bar",
	"nightlife",
	"no_drinks",
	"sports_bar",
	"no_adult_content",
	"explicit",
	"sword_rose",
	"pill",
	"pill_off",
	"prescriptions",
	"pregnant_woman",
	"pregnancy"
]

class IconMapEntry(TypedDict):
	page: str
	start_x: int
	start_y: int
	finish_x: int
	finish_y: int

class Icon(TypedDict):
	name: str
	size: Size
	style: Style
	scale: Scale
	width: int
	index: int
	category: str
	path: str
	export_group: str

def invert_image(image: Image) -> Image:
	# Ensure the image is in RGB mode for compatibility
	image = image.convert("RGBA")

	# Iterate through each pixel and invert the color
	inverted_pixels = []
	width, height = image.size

	for y in range(height):
		for x in range(width):
			r, g, b, a = image.getpixel((x, y))
			inverted_r = 255 - r
			inverted_g = 255 - g
			inverted_b = 255 - b
			inverted_pixels.append((inverted_r, inverted_g, inverted_b, a))

	# Create a new image with the inverted pixels
	inverted_image = Image.new("RGBA", (width, height))
	inverted_image.putdata(inverted_pixels)

	return inverted_image

def organize_to_spritesheets() -> None:
	export_groups: dict[str, list[Icon]] = {}
	
	for category in os.listdir(PNG_PATH):
		for icon_name in os.listdir(f"{PNG_PATH}/{category}"):
			if not icon_name in BAD_ICONS:
				for icon_style in os.listdir(f"{PNG_PATH}/{category}/{icon_name}"):
					style: Style = DIR_TO_STYLE[icon_style];
					for icon_size in os.listdir(f"{PNG_PATH}/{category}/{icon_name}/{icon_style}"):
						size: Size = DP_TO_SIZE[icon_size];
						# if size <= 48:
						for icon_scale in os.listdir(f"{PNG_PATH}/{category}/{icon_name}/{icon_style}/{icon_size}"):
							scale: Scale = SCALE_TO_SCALE[icon_scale]
							# if scale <= 1:
							for file in os.listdir(f"{PNG_PATH}/{category}/{icon_name}/{icon_style}/{icon_size}/{icon_scale}"):
								export_group = f"{style}_{size}_{scale}"
								if not export_group in export_groups:
									export_groups[export_group] = []

								export_groups[export_group].append({
									"size": size,
									"style": style,
									"width": size * scale,
									"index": len(export_groups[export_group])+1,
									"scale": scale,
									"name": icon_name,
									"category": category,
									"path": f"{PNG_PATH}/{category}/{icon_name}/{icon_style}/{icon_size}/{icon_scale}/{file}",
									"export_group": export_group,
								})

	icon_maps: dict[str, dict[str, IconMapEntry]] = {}
	shutil.rmtree(OUT_DIR)
	total_page_count = 0
	os.makedirs(OUT_MAP_DIR)
	os.makedirs(OUT_IMG_DIR)
	for group_name, icon_list in export_groups.items():
		icon_maps[group_name] = {}
		dir_path = f"{OUT_IMG_DIR}/{group_name}"		
		
		os.makedirs(dir_path)

		width: int = icon_list[0]["width"]
		icons_per_row = math.floor(MAX_DIM / width)
		icons_per_page = icons_per_row*icons_per_row
		pages_needed = math.ceil(len(icon_list)/icons_per_page)

		icon_index = 0

		for page_num in range(pages_needed):
			page_path = f"{dir_path}/page{page_num}.png"
			print(f"writing {group_name} sheet {page_num+1}/{pages_needed}")
			out_image = Image.new('RGBA', (MAX_DIM, MAX_DIM), (0, 0, 0, 0))
			total_page_count += 1
			
			for icon_num in range(icons_per_page):
				if icon_index <= len(icon_list)-1:
					row_index = icon_num % icons_per_row
					column_index = math.floor(icon_num / icons_per_row)

					icon_data = icon_list[icon_index]

					icon_image = Image.open(icon_data["path"])
					inverted_image = invert_image(icon_image)
					icon_name = icon_data["name"]

					icon_map_entry: IconMapEntry = {
						"page": page_path,
						"start_x": row_index*width,
						"start_y": column_index*width,
						"finish_x": (row_index+1)*width,
						"finish_y": (column_index+1)*width
					}

					assert icon_map_entry["start_x"] >= 0, icon_map_entry
					assert icon_map_entry["start_x"] <= MAX_DIM, icon_map_entry
					assert icon_map_entry["start_y"] >= 0, icon_map_entry
					assert icon_map_entry["start_y"] <= MAX_DIM, icon_map_entry
					assert icon_map_entry["finish_x"] >= 0, icon_map_entry
					assert icon_map_entry["finish_x"] <= MAX_DIM, icon_map_entry
					assert icon_map_entry["finish_y"] >= 0, icon_map_entry
					assert icon_map_entry["finish_y"] <= MAX_DIM, icon_map_entry

					icon_maps[group_name][icon_name] = icon_map_entry

					out_image.paste(inverted_image, (icon_map_entry["start_x"], icon_map_entry["start_y"]))

				icon_index += 1

			out_image.save(page_path)
				
		with open(f"{OUT_MAP_DIR}/{group_name}.json", "w") as map_file:
			map_file.write(json.dumps(icon_maps[group_name], indent=5))

	print(f"total sheet count: {total_page_count}")

# def upload_spritesheets() -> None:
# 	print("")

def upload_image(file_path: str, name: str) -> int:
	print(f"uploading {file_path} as {name}")	

	# Make the POST request with multipart data
	post_response = requests.post(
		'https://apis.roblox.com/assets/v1/assets', 
		data={
			"request": json.dumps({
				"assetType": "Decal",
				"displayName": name,
				"description": "spritesheet used in the wally package nightcycle/material-icons",
				"creationContext": {
					"creator": {
						"groupId": 4181328
					}
				}
			}),
		},
		headers={
			'x-api-key': AUTH_KEY
		},
		files = {'fileContent': (file_path, open(file_path, 'rb').read(), 'image/png')}
		
	)
	time.sleep(1)
	# Check the response
	if post_response.status_code == 200:
		post_data = json.loads(post_response.content)
		while True:
			operation_id = post_data["operationId"]
			get_response = requests.get(
				f"https://apis.roblox.com/assets/v1/operations/{operation_id}",
				headers={
					'x-api-key': AUTH_KEY
				},
			)
			if get_response.status_code == 200:
				get_data = json.loads(get_response.content)
				if get_data["done"] == True:
					return int(get_data["response"]["assetId"])
				time.sleep(1)
			else:
				raise Exception(f"Error: {get_response.status_code} - {get_response.text}")	
	else:
		raise Exception(f"Error: {post_response.status_code} - {post_response.text}")

def upload_sheets() -> None:
	asset_ids = {}
	for group in os.listdir(OUT_IMG_DIR):
		for page in os.listdir(f"{OUT_IMG_DIR}/{group}"):
			page_path = f"{OUT_IMG_DIR}/{group}/{page}"

			def try_forever():
				try:
					asset_ids[page_path] = upload_image(page_path, page_path.replace(OUT_IMG_DIR+"/", "").replace(".png", "").replace("/", "_").lower().replace("page", "p"));
				except:
					time.sleep(5)
					try_forever()

			try_forever()

	with open(ASSET_ID_PATH, "w") as asset_file:
		asset_file.write(json.dumps(asset_ids, indent=5))

def convert_to_decal_ids() -> None:
	asset_ids: dict[str, int] = json.loads(open(ASSET_ID_PATH, "r").read())
	id_list = list(asset_ids.values())
	id_txt = json.dumps(id_list).replace("[", "{").replace("]", "}")
	open(DECAL_SCRIPT_PATH, "w").write(
		f"local AssetIds = {id_txt}"+"""
		local HttpService = game:GetService("HttpService")
		local InsertService = game:GetService("InsertService")

		local Results: {[number]: number} = {}

		for i, assetId in ipairs(AssetIds) do
			local model = InsertService:LoadAsset(assetId)

			local decal = model:FindFirstChildOfClass("Decal")
			assert(decal, `bad decal for {assetId}`)

			local decalIdStr = decal.Texture:gsub("%p", ""):gsub("%a", "")
			local decalId = tonumber(decalIdStr)
			assert(decalId, `bad decalId for {assetId}`)
			Results[assetId] = decalId
		end

		print(HttpService:JSONEncode(Results))
	""")

	os.system(f"rojo build --output {DECAL_PLACE_PATH}")
	os.system(f"run-in-roblox --place {DECAL_PLACE_PATH} --script {DECAL_SCRIPT_PATH} > {DECAL_ID_PATH}")

def build_script() -> None:
	decal_ids = json.loads(open(DECAL_ID_PATH, "r").read())
	asset_ids = json.loads(open(ASSET_ID_PATH, "r").read())

	path_ids: dict[str, int] = {}
	for page_path, asset_id in asset_ids.items():
		path_ids[page_path] = decal_ids[str(asset_id)]

	if os.path.exists(LUAU_OUT_DIR):
		shutil.rmtree(LUAU_OUT_DIR)

	os.makedirs(LUAU_OUT_DIR)

	tree: dict[str, dict[str, dict[str, str]]] = {}

	for map_path in os.listdir(OUT_MAP_DIR):
		map_data: dict[str, IconMapEntry] = json.loads(open(f"{OUT_MAP_DIR}/{map_path}", "r").read())

		luau_data: dict[str, dict] = {}

		for icon_name, icon_data in map_data.items():
			decal_id = path_ids[icon_data["page"]]
			offset_x = icon_data["start_x"]
			offset_y = icon_data["start_y"]
			size_x = icon_data["finish_x"] - offset_x
			size_y = icon_data["finish_y"] - offset_y
			
			luau_data[icon_name] = {
				"Image": f"rbxassetid://{decal_id}",
				"ImageRectOffset": mark_as_literal(f"Vector2.new({offset_x}, {offset_y})"),
				"ImageRectSize": mark_as_literal(f"Vector2.new({size_x}, {size_y})"),
			}

		content = [
			"--!strict",
			"-- this script is auto generated, don't manually change it please",
			f"return {from_dict(luau_data)}",
		]

		map_name = map_path.replace(".json", "")

		open(f"{LUAU_OUT_DIR}/{map_name}.luau", "w").write("\n".join(content))

		map_style = map_name.split("_")[0].replace("TwoTone", "two_tone")
		map_dp = map_name.split("_")[1]
		map_scale = map_name.split("_")[2]

		map_path = f"{map_style.lower()}/dp_{map_dp}/scale_{map_scale}"
		dpath.new(
			tree, 
			map_path, 
			mark_as_literal(f"require(script:WaitForChild(\"{map_name}\"))")
		)
	
	# print(json.dumps(tree, indent=5))
	open(f"{LUAU_OUT_DIR}/init.luau", "w").write("\n".join([
		"--!strict",
		"-- search for icons here: https://fonts.google.com/icons",
		"-- this script is auto generated, don't manually change it please",
		f"return {from_dict(tree)}",
	]))

def main():
	organize_to_spritesheets()
	upload_sheets()
	convert_to_decal_ids()
	build_script()

main()