FROM python:3.11-slim-buster

# Set the working directory in the container
WORKDIR /usr/src/app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the current directory contents into the container at /usr/src/app
COPY *.py .

# Run bot.py when the container launches
CMD ["python", "bot.py"]

