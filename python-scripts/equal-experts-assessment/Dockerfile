FROM python:3.12-slim

ARG USERNAME=vasant
ARG USER_UID=1001
ARG USER_GID=$USER_UID

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py .
RUN groupadd --gid $USER_GID $USERNAME \
    && useradd --uid $USER_UID --gid $USER_GID -m $USERNAME

USER $USERNAME
EXPOSE 8080

## Disable for Production
CMD ["python", "app.py"]



## Enable for Production (Recommended)
##CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "1", "app:app"]