#!/bin/sh

source ~/miniconda3/etc/profile.d/conda.sh
conda activate crispranalysis

echo "the little bash start!"

echo "now adapterremoval 1"

AdapterRemoval --file1 R1.fq.gz --file2 R2.fq.gz --barcode-list barcodenova.txt --demultiplex-only --basename fwd

echo "now adapterremoval 2"

#AdapterRemoval --file1 R2.fq.gz --file2 R1.fq.gz --barcode-list barcodenova.txt --demultiplex-only --basename rev

AdapterRemoval --file1 fwd.unidentified_2.fastq --file2 fwd.unidentified_1.fastq --barcode-list barcodenova.txt --demultiplex-only --basename rev

echo "now combine fwd and rev"

for i in A B C D E F;
	do
		for j in {1..6};
			do
				for k in 1 2	
					do
						cat rev.$i$j.pair$k.fastq >> fwd.$i$j.pair$k.fastq
					done
			done
	done

echo "now clean up"

rm -f *.settings
#rm -f *unidentified*
rm -f *rev*
find . -name "*" -type f -size 0c | xargs -n 1 rm -f

echo "now CRISPResso time! have a cup of coffee!"

for i in A B C D E F;
	do
		for j in {1..6};
		do
			CRISPResso -r1 fwd.$i$j.pair1.fastq -r2 fwd.$i$j.pair2.fastq -a TGCTCAGATGAACAACGGCTCCAACCCCATGTTCAGAAATATCAACGTGTACGATCTCTTCGTCTGGATGCATTATTATGCCTCTCGAGACACACTCTTAGGTGGCTCCAATGTGTGGAGAGACATTGATTTTGCCCATGAAGCCCCTGGTTTTCTGCCTTGGCATCGTGCTTTTCTGCTGCTGTGGGAACGTGAGATACAGAAGATAACAGGTGATGAGAATTTCACCATCCCCTACTGGGACTGGCGAGATGCAGAGGACTGTGTGATCTGCACTGATGAATACATGGGTGGCCAACACCCCACCAACCCTAATTTACTCAGCCCAGCATCATTTTTCTCCTCATGGCAGgtaaggacaggcaaagggatgaaggtaaggggagggca -g TCGCCAGTCCCAGTAGGGGA -an tyre1 -gn sgrna3 --trim_sequences  --trimmomatic_options_string SLIDINGWINDOW:4:10 -w 1 --ignore_substitutions --plot_histogram_outliers --min_frequency_alleles_around_cut_to_plot 0.01 -o ./results;
		done;
	done;

echo "all done."
