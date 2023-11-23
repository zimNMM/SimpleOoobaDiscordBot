import settings
import io
import random
import discord
from discord.ext import commands
from discord.app_commands import describe
import httpx

def run():
    intents = discord.Intents.default()
    intents.message_content = True
    client = discord.Client(intents=intents)

    
    bot = commands.Bot(command_prefix="/",intents=intents)
    @bot.event
    async def on_ready():
        print(bot.user)

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

    
                if len(generated_text) <= 2000:
                    await interaction.followup.send(generated_text)
                else:
                    file = discord.File(fp=io.BytesIO(generated_text.encode("utf-8")), filename="message.txt")
                    await interaction.followup.send(file=file)
            else:
                await interaction.followup.send("Error: Unable to get a response from the API.")

        except Exception as e:
            await interaction.followup.send(f"An error occurred: {str(e)}")



        
        

    bot.run(settings.DISCORD_API_SECRET)
if __name__ == "__main__":
    run();