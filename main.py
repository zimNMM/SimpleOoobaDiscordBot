import settings
import io
import discord
from discord.ext import commands
from discord.app_commands import describe
from discord import app_commands
import httpx
import base64
from PIL import Image

def run():
    intents = discord.Intents.default()
    intents.message_content = True
    client = discord.Client(intents=intents)
    tree = app_commands.CommandTree(client)
    bot = commands.Bot(command_prefix="/",intents=intents)
    
    @bot.event
    async def on_ready():
        print(bot.user)
        sync_commands = await bot.tree.sync()

    @bot.tree.command(name="say", description="Ask a model a question.")
    @describe(prompt="Your prompt.")
    async def ask(interaction, prompt: str):
        try:
            await interaction.response.defer()
            api_url = "http://127.0.0.1:5000/v1/completions"

        
            data = {
                "prompt": f"### Input:\n{prompt}\n\n### Response:\n",
                "temperature": 0.5,  
                "max_tokens": 200
            }

        
            async with httpx.AsyncClient() as client:
                response = await client.post(api_url, json=data)

        
            if response.status_code == 200:
                response_data = response.json()
                full_text = response_data.get("choices")[0].get("text")

    
                generated_text = full_text.split("### Response:\n")[-1].strip()

    
                if len(generated_text) <= 1500:
                    await interaction.followup.send(generated_text)
                else:
                    file = discord.File(fp=io.BytesIO(generated_text.encode("utf-8")), filename="message.txt")
                    await interaction.followup.send(file=file)
            else:
                await interaction.followup.send("Error: Unable to get a response from the API.")

        except Exception as e:
            await interaction.followup.send(f"An error occurred: {str(e)}")

    @bot.tree.command(name="imagine", description="Generate an image from a prompt.")   
    @describe(prompt="Your image prompt.")
    async def imagine(interaction, prompt: str):
        try:
            await interaction.response.defer()

            url = "http://127.0.0.1:7860/sdapi/v1/txt2img"
            payload = {
                "prompt": prompt,
                "steps": 25
            }

            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=payload)

                if response.status_code != 200:
                    await interaction.followup.send("Error: Unable to generate an image.")
                    return

                r = response.json()
                image_data = base64.b64decode(r['images'][0])

                with io.BytesIO(image_data) as image_io:
                    image_io.seek(0)
                    discord_file = discord.File(fp=image_io, filename="image.png")
                    await interaction.followup.send(file=discord_file)

        except Exception as e:
            await interaction.followup.send(f"An error occurred: {str(e)}")


        
        

    bot.run(settings.DISCORD_API_SECRET)
if __name__ == "__main__":
    run();
