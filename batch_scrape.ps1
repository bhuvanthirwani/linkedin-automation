# Batch Scrape Script

Write-Host "Starting Batch Scrape Job 1: Engineering Manager"
python run.py --mode Scrapping --keywords "Engineering Manager" --location "90000084" --start-page 3 --pages 25 --max-connections 250

Write-Host "Job 1 Completed. Waiting 180 seconds..."
Start-Sleep -Seconds 180

Write-Host "Starting Batch Scrape Job 2: Director of Software Engineering"
python run.py --mode Scrapping --keywords "Director of Software Engineering" --location "90000084" --start-page 1 --pages 25 --max-connections 250

Write-Host "Job 2 Completed. Waiting 180 seconds..."
Start-Sleep -Seconds 180

Write-Host "Starting Batch Scrape Job 3: Staff Software Engineer"
python run.py --mode Scrapping --keywords "Staff Software Engineer" --location "90000084" --start-page 1 --pages 25 --max-connections 250

Write-Host "Starting Batch Scrape Job 4: Engineering Manager"
python run.py --mode Scrapping --keywords "Engineering Manager" --location "104116203" --start-page 1 --pages 25 --max-connections 250

Write-Host "Job 4 Completed. Waiting 180 seconds..."
Start-Sleep -Seconds 180

Write-Host "Starting Batch Scrape Job 5: Director of Software Engineering"
python run.py --mode Scrapping --keywords "Director of Software Engineering" --location "104116203" --start-page 1 --pages 25 --max-connections 250

Write-Host "Job 5 Completed. Waiting 180 seconds..."
Start-Sleep -Seconds 180

Write-Host "Starting Batch Scrape Job 6: Staff Software Engineer"
python run.py --mode Scrapping --keywords "Staff Software Engineer" --location "104116203" --start-page 1 --pages 25 --max-connections 250

Write-Host "Job 6 Completed. Waiting 180 seconds..."

Write-Host "All Jobs Completed."
