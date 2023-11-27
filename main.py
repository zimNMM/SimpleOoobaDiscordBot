import settings
import io
import discord
from discord.ext import commands
from discord.app_commands import describe
from discord import app_commands
import httpx
import base64
import sqlite3
from aiohttp import client_exceptions
import platform
import psutil
import GPUtil

ooba_alpaca= "Below is an instruction that describes a task, Write a response that appropriately completes the request."
ooba_url = "http://127.0.0.1:5000/v1/completions"
sd_url_txt2img = "http://127.0.0.1:7861/sdapi/v1/txt2img"
sd_url_lora = "http://127.0.0.1:7861/sdapi/v1/loras"
nsfw_api_key = 'NSFW-API-KEY' #nsfw-categorize.it

async def get_system_info():
    info = {
        'platform': platform.system(),
        'platform_release': platform.release(),
        'platform_version': platform.version(),
        'architecture': platform.machine(),
        'hostname': platform.node(),
        'processor': platform.processor(),
        'memory': {
            'total': psutil.virtual_memory().total,
            'available': psutil.virtual_memory().available,
            'percent': psutil.virtual_memory().percent
        },
        'gpus': [{'name': gpu.name, 'load': gpu.load, 'total_memory': gpu.memoryTotal, 'temperature': gpu.temperature} for gpu in GPUtil.getGPUs()]
    }
    return info

def setup_database():
    conn = sqlite3.connect('bot_settings.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS settings (setting_name TEXT PRIMARY KEY, setting_value TEXT)''')
    c.execute('''INSERT OR IGNORE INTO settings (setting_name, setting_value) VALUES ('nsfw_enabler', 'True')''')
    conn.commit()
    conn.close()

def run():
    setup_database()
    intents = discord.Intents.default()
    intents.message_content = True
    client = discord.Client(intents=intents)
    tree = app_commands.CommandTree(client)
    bot = commands.Bot(command_prefix="/",intents=intents)
    
    
    async def check_nsfw(image_io):
        url = 'https://nsfw-categorize.it/api/upload'
        headers = {'NSFWKEY': nsfw_api_key}
        files = {'image': ('image.png', image_io, 'image/png')}
    
        async with httpx.AsyncClient(timeout=360.0) as client:
            response = await client.post(url, headers=headers, files=files)
    
        if response.status_code == 200:
            result = response.json()
            return result.get("status") == "OK" and result["data"].get("nsfw")
        else:
            raise Exception("NSFW check failed")


    @bot.event
    async def on_ready():
        print(bot.user)
        sync_commands = await bot.tree.sync()

    @bot.tree.command(name="sysinfo", description="System info.")
    async def sysinfo(interaction):
        try:
            await interaction.response.defer()

            info = await get_system_info()
            info_message = f"System Information:\n"
            info_message += f"Platform: {info['platform']} {info['platform_release']} {info['platform_version']}\n"
            info_message += f"Architecture: {info['architecture']}\n"
            info_message += f"Processor: {info['processor']}\n"
            info_message += f"Memory Total: {info['memory']['total']} Available: {info['memory']['available']} Percent: {info['memory']['percent']}\n"
            if info['gpus']:
                for gpu in info['gpus']:
                    info_message += f"GPU: {gpu['name']} Load: {gpu['load']} Memory: {gpu['total_memory']} Temperature: {gpu['temperature']}\n"
            else:
                info_message += "No GPU information available.\n"

            await interaction.followup.send(info_message)

        except Exception as e:
            await interaction.followup.send(f"An error occurred: {str(e)}")

    @bot.tree.command(name="say", description="Ask a model a question.")
    @describe(prompt="Your prompt.")
    async def ask(interaction, prompt: str):
        try:
            await interaction.response.defer()

            ooba_payload = {
                "prompt": f"{ooba_alpaca}### Input:\n{prompt}\n\n### Response:\n",
                "temperature": 0.5,  
                "max_tokens": 200
            }
        
            async with httpx.AsyncClient() as client:
                response = await client.post(ooba_url, json=ooba_payload)

            if response.status_code == 200:
                response_data = response.json()
                full_text = response_data.get("choices")[0].get("text")

                await interaction.followup.send(full_text)

            else:
                await interaction.followup.send("Error: Unable to get a response from the API.")

        except Exception as e:
            await interaction.followup.send(f"An error occurred: {str(e)}")

    @bot.tree.command(name="imagine", description="Generate an image from a prompt.")   
    @describe(prompt="Your image prompt.")
    @describe(codeformer="Set to True to enable Codeformer restoration.")
    @describe(adetailer="Set to True to enable Adetailer extension.")
    @describe(n="Number of batch photos to generate max 8.")
    async def imagine(interaction, prompt: str, width: int = 512, height: int = 512, n: int =1, codeformer: str = "False",adetailer: str = "False",):
        try:
            await interaction.response.defer()
            codeformer_bool = codeformer.lower() == "true"
            adetailer_bool = adetailer.lower() == "true"

            sd_payload = {
                "prompt": prompt,
                "steps": 30,
                "width": width,
                "height": height,
                "batch_size": n,
                "restore_faces": codeformer_bool,
                "alwayson_scripts": {
                    "ADetailer": {
                        "args": [
                            adetailer_bool,  
                            {
                        "ad_model": "face_yolov8n.pt"
                            }
                        ]
                    }
                }
            }




            async with httpx.AsyncClient(timeout=360.0) as client:
                response = await client.post(sd_url_txt2img, json=sd_payload)

                if response.status_code != 200:
                    await interaction.followup.send("Error: Unable to generate an image.")
                    return

                r = response.json()
                images = r.get('images', [])

                conn = sqlite3.connect('bot_settings.db')
                c = conn.cursor()
                c.execute('''SELECT setting_value FROM settings WHERE setting_name = 'nsfw_enabler' ''')
                nsfw_enabler = c.fetchone()[0] == 'True' 
                conn.close()

                for idx, img_base64 in enumerate(images):
                    image_data = base64.b64decode(img_base64)
                    with io.BytesIO(image_data) as image_io:
                        if nsfw_enabler:
                            is_nsfw = await check_nsfw(image_io)
                            if is_nsfw:
                                await interaction.followup.send(f"Image detected as NSFW. Not displaying.")
                                continue
                            image_io.seek(0)

                        discord_file = discord.File(fp=image_io, filename=f"image_{idx}.png")
                        await interaction.followup.send(file=discord_file)

        except Exception as e:
            await interaction.followup.send(f"An error occurred: {str(e)}")

    @bot.tree.command(name="getloras", description="Get Loras names.")
    async def getloras(interaction):
        try:
            await interaction.response.defer()

            async with httpx.AsyncClient() as client:
                response = await client.get(sd_url_lora)

                if response.status_code != 200:
                    await interaction.followup.send("Error: Unable to get Loras.")
                    return

                loras_data = response.json()

                names = [f"<lora:{lora.get('name', '')}:1>" for lora in loras_data]
                names_str = ' '.join(names)

            await interaction.followup.send(names_str)

        except Exception as e:
            await interaction.followup.send(f"An error occurred: {str(e)}")

    @bot.tree.command(name="toggle_nsfw", description="Toggle NSFW check on/off.")
    async def toggle_nsfw(interaction):
        conn = sqlite3.connect('bot_settings.db')
        c = conn.cursor()
    
        c.execute('''SELECT setting_value FROM settings WHERE setting_name = 'nsfw_enabler' ''')
        current_value = c.fetchone()[0] == 'True'
        new_value = 'False' if current_value else 'True'

        c.execute('''UPDATE settings SET setting_value = ? WHERE setting_name = 'nsfw_enabler' ''', (new_value,))
        conn.commit()
        conn.close()

        await interaction.response.send_message(f"NSFW check is now {'enabled' if new_value == 'True' else 'disabled'}.")
    try:
        bot.run(settings.DISCORD_API_SECRET)
    except client_exceptions.ClientConnectorError as e:
        print(f"Network error: Unable to connect to Discord.")
    except Exception as e:
        print(f"An unexpected error occurred: {str(e)}")

if __name__ == "__main__":
    run()
