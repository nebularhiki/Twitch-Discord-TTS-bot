# Pretext this is extremely bad and a rough start for this project
# It will eventually evolve to be something hopefully better
import asyncio
import socketserver
import string
import sys
import threading
import time

import boto3
import discord
from decouple import config
from discord.ext import commands

# The module holding the list of filtered words
# It isn't the best method but it works, might switch to CSV eventually
from filter.filter import nonowords


# Where you want the mp3 output to be located
output_path = "python/output.mp3"
# The name of the bot which is the basic prefix that will be used in discord
bot_name = "Aia"
# Sound board folder location
sound_board = "soundboard/"


intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.voice_states = True
bot = commands.Bot(intents=intents, command_prefix=f"{bot_name} ")


# The UDP Handler for interfacing with streamer.bot
# Plays the essage inputed in the twitch chat message
class MyUDPHandler(socketserver.DatagramRequestHandler):
    def handle(self):
        # for line terminated messages
        msgRecvd = self.rfile.readline().strip()
        msg = msgRecvd.decode("utf-8").lower()
        print(f"The Message is '{msgRecvd.decode('utf-8')}'")
        text = check_filter(msg)
        text_to_mp3(text)
        play_twitch_msg(output_path)


# Checks the filtered list to sort out words that you wish not to be said
def check_filter(text):
    msg = text.translate(str.maketrans("", "", string.punctuation)).lower().split()
    print(msg)
    for i in msg:
        print(i)
        if i in nonowords:
            print(f"{i} is a no no word")
            return "filtered"
    return text


# Plays the audio from the twitch chat message
def play_twitch_msg(audio):
    voice_client: discord.VoiceClient = discord.utils.get(bot.voice_clients)
    print("attempting to play")
    voice_client.play(discord.FFmpegPCMAudio(executable="ffmpeg", source=audio))
    print("audio played")
    while voice_client.is_playing():
        time.sleep(0.1)
    print("done")


# Plays the audio in channel same as play_twitch_msg but async to work in other async functions
async def play_audio_in_channel(audio):
    voice_client: discord.VoiceClient = discord.utils.get(bot.voice_clients)
    print("attempting to play")
    voice_client.play(discord.FFmpegPCMAudio(executable="ffmpeg", source=audio))
    print("audio played")
    while voice_client.is_playing():
        await asyncio.sleep(0.1)
    print("done")


# Takes the inputed text and converts it into the audio file that will be played
def text_to_mp3(text):
    session = boto3.Session(
        aws_access_key_id=config("AWS_TOKEN"),
        aws_secret_access_key=config("AWS_PRIVATE_TOKEN"),
        region_name="us-east-1",
    )
    polly = session.client("polly")
    response = polly.synthesize_speech(
        Text=text, OutputFormat="mp3", VoiceId="Justin", Engine="neural"
    )
    with open(output_path, "wb") as file:
        file.write(response["AudioStream"].read())
    print("mp3 file saved")


### BOT COMMANDS


# Prints message in console signalling when the bot is ready
@bot.event
async def on_ready():
    print("We have logged in as {0.user}".format(bot))


# "{bot_name} {function} {input}" is how these commands are used in discord


# Joins voice channel user is actively in
@bot.command()
async def join(ctx):
    print("Running join")
    try:
        voicech = ctx.author.voice.channel
        if voicech is not None:
            await ctx.send("Joining...")
            await voicech.connect(
                timeout=30, reconnect=True, cls=(discord.voice_client.VoiceClient)
            )
            await ctx.send("Joined.")
        else:
            await ctx.send(ctx.author + "is not in a channel")
    except RuntimeError:
        await ctx.send("Something went wrong...")
    except AttributeError:
        await ctx.send("Something went wrong...")


# Says whatever the user inputs after the say command
@bot.command()
async def say(ctx, *, text):
    q = []
    print(f"Adding {text} to queue...")
    t = check_filter(text)
    q.append(str(t))
    for i in q:
        text_to_mp3(i)
        await play_audio_in_channel(output_path)
    q[:] = []


# plays the audio the user inputed
# Requires the audio files to be formated in snake_case
@bot.command()
async def play(*, text):
    audio = f"{sound_board}{text}.mp3".lower().replace(" ", "_")
    await play_audio_in_channel(audio)


# Leaves the channel the bot is currently in
@bot.command()
async def leave(ctx):
    print("Running Leave")
    if ctx.voice_client:
        await ctx.send("Leaving...")
        await ctx.guild.voice_client.disconnect()
        await ctx.send("Left")
    else:
        await ctx.send("I'm not in a channel")


# The udpr server this isn't my own code but and I can't remember where I found it... thanks whoever made this!
def udpr():  # we specify the address and port we want to listen on
    listen_addr = ("0.0.0.0", 414)

    # with allowing to reuse the address we dont get into problems running it consecutively sometimes
    socketserver.UDPServer.allow_reuse_address = True

    # register our class
    serverUDP = socketserver.UDPServer(listen_addr, MyUDPHandler)
    serverUDP.serve_forever()


# run bot
def discord_bot():
    bot.run(config("BOT_TOKEN"))


# Threading udpr and the bot so they are both working together
# Need to eventually separate this so threading isn't needed
def main(argv):
    t1 = threading.Thread(target=udpr)
    t2 = threading.Thread(target=discord_bot)

    t1.daemon = True
    t2.daemon = True

    t1.start()
    t2.start()

    try:
        while t1.is_alive() and t2.is_alive():
            time.sleep(60)
        print("Exited")
    except KeyboardInterrupt:
        print("Shutting down")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
