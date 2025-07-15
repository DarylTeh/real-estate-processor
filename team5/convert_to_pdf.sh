#!/bin/bash

# Convert text files to PDF using pandoc
echo "Converting text files to PDF..."

# Settlement Document
echo "Creating Settlement Document PDF..."
pandoc /home/ubuntu/environment/GameDay/team5/real-estate-processor/team5/sample_settlement_document.txt \
  -o /home/ubuntu/environment/GameDay/team5/real-estate-processor/team5/settlement_document.pdf \
  --pdf-engine=pdflatex \
  -V geometry:margin=1in \
  -V fontsize=11pt

# Income Verification
echo "Creating Income Verification PDF..."
pandoc /home/ubuntu/environment/GameDay/team5/real-estate-processor/team5/sample_income_verification.txt \
  -o /home/ubuntu/environment/GameDay/team5/real-estate-processor/team5/income_verification.pdf \
  --pdf-engine=pdflatex \
  -V geometry:margin=1in \
  -V fontsize=11pt

# Purchase Agreement (combine both parts)
echo "Combining Purchase Agreement parts..."
cat /home/ubuntu/environment/GameDay/team5/real-estate-processor/team5/sample_purchase_agreement.txt \
    /home/ubuntu/environment/GameDay/team5/real-estate-processor/team5/sample_purchase_agreement_part2.txt \
    > /home/ubuntu/environment/GameDay/team5/real-estate-processor/team5/sample_purchase_agreement_combined.txt

echo "Creating Purchase Agreement PDF..."
pandoc /home/ubuntu/environment/GameDay/team5/real-estate-processor/team5/sample_purchase_agreement_combined.txt \
  -o /home/ubuntu/environment/GameDay/team5/real-estate-processor/team5/purchase_agreement.pdf \
  --pdf-engine=pdflatex \
  -V geometry:margin=1in \
  -V fontsize=11pt

echo "Creating additional Settlement Document samples..."
# Create a second settlement document with slight variations
sed 's/John and Jane Smith/Michael and Sarah Johnson/g; s/450,000.00/525,000.00/g' \
  /home/ubuntu/environment/GameDay/team5/real-estate-processor/team5/sample_settlement_document.txt \
  > /home/ubuntu/environment/GameDay/team5/real-estate-processor/team5/sample_settlement_document2.txt

pandoc /home/ubuntu/environment/GameDay/team5/real-estate-processor/team5/sample_settlement_document2.txt \
  -o /home/ubuntu/environment/GameDay/team5/real-estate-processor/team5/settlement_document2.pdf \
  --pdf-engine=pdflatex \
  -V geometry:margin=1in \
  -V fontsize=11pt

# Create a third settlement document with slight variations
sed 's/John and Jane Smith/Robert and Emily Wilson/g; s/450,000.00/375,000.00/g' \
  /home/ubuntu/environment/GameDay/team5/real-estate-processor/team5/sample_settlement_document.txt \
  > /home/ubuntu/environment/GameDay/team5/real-estate-processor/team5/sample_settlement_document3.txt

pandoc /home/ubuntu/environment/GameDay/team5/real-estate-processor/team5/sample_settlement_document3.txt \
  -o /home/ubuntu/environment/GameDay/team5/real-estate-processor/team5/settlement_document3.pdf \
  --pdf-engine=pdflatex \
  -V geometry:margin=1in \
  -V fontsize=11pt

echo "Creating additional Income Verification samples..."
# Create a second income verification with slight variations
sed 's/Michael Rodriguez/Jennifer Thompson/g; s/145,000.00/120,000.00/g' \
  /home/ubuntu/environment/GameDay/team5/real-estate-processor/team5/sample_income_verification.txt \
  > /home/ubuntu/environment/GameDay/team5/real-estate-processor/team5/sample_income_verification2.txt

pandoc /home/ubuntu/environment/GameDay/team5/real-estate-processor/team5/sample_income_verification2.txt \
  -o /home/ubuntu/environment/GameDay/team5/real-estate-processor/team5/income_verification2.pdf \
  --pdf-engine=pdflatex \
  -V geometry:margin=1in \
  -V fontsize=11pt

# Create a third income verification with slight variations
sed 's/Michael Rodriguez/Christopher Davis/g; s/145,000.00/185,000.00/g' \
  /home/ubuntu/environment/GameDay/team5/real-estate-processor/team5/sample_income_verification.txt \
  > /home/ubuntu/environment/GameDay/team5/real-estate-processor/team5/sample_income_verification3.txt

pandoc /home/ubuntu/environment/GameDay/team5/real-estate-processor/team5/sample_income_verification3.txt \
  -o /home/ubuntu/environment/GameDay/team5/real-estate-processor/team5/income_verification3.pdf \
  --pdf-engine=pdflatex \
  -V geometry:margin=1in \
  -V fontsize=11pt

echo "Creating additional Purchase Agreement samples..."
# Create a second purchase agreement with slight variations
sed 's/David and Sarah Thompson/Kevin and Lisa Martinez/g; s/1,850,000.00/1,250,000.00/g' \
  /home/ubuntu/environment/GameDay/team5/real-estate-processor/team5/sample_purchase_agreement_combined.txt \
  > /home/ubuntu/environment/GameDay/team5/real-estate-processor/team5/sample_purchase_agreement2.txt

pandoc /home/ubuntu/environment/GameDay/team5/real-estate-processor/team5/sample_purchase_agreement2.txt \
  -o /home/ubuntu/environment/GameDay/team5/real-estate-processor/team5/purchase_agreement2.pdf \
  --pdf-engine=pdflatex \
  -V geometry:margin=1in \
  -V fontsize=11pt

# Create a third purchase agreement with slight variations
sed 's/David and Sarah Thompson/Thomas and Amanda Brown/g; s/1,850,000.00/2,100,000.00/g' \
  /home/ubuntu/environment/GameDay/team5/real-estate-processor/team5/sample_purchase_agreement_combined.txt \
  > /home/ubuntu/environment/GameDay/team5/real-estate-processor/team5/sample_purchase_agreement3.txt

pandoc /home/ubuntu/environment/GameDay/team5/real-estate-processor/team5/sample_purchase_agreement3.txt \
  -o /home/ubuntu/environment/GameDay/team5/real-estate-processor/team5/purchase_agreement3.pdf \
  --pdf-engine=pdflatex \
  -V geometry:margin=1in \
  -V fontsize=11pt

echo "All PDFs created successfully!"
ls -la *.pdf
