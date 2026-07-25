# Use a lightweight Python image
FROM python:3.12-slim

# Set the working directory inside the container
WORKDIR /app

# Copy requirements and install them
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of your backend code
COPY . .

# Expose the port FastAPI runs on (based on your PDF, you use 3033)
EXPOSE 3033

# Command to run the app
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "3033"]