The steps taken to attempt this are:

1) Collect data from the https://openneuro.org/datasets/ds001506/versions/1.3.1 website along with the tsv, json and nii files.
2) Take data from JSON file and correlate it with tsv files to indicate relevant information.
3) There was a problem of correlating this data with the voxel positions in the fMRI images.

When the above mentioned method did not work, we used a pre-trained VGG19 model which was used as a decoder for the f-MRI scans. (https://journals.plos.org/ploscompbiol/article?id=10.1371/journal.pcbi.1006633). Using this pre-trained model, we were able to generate the required image using our algorithm as implemented in the python file. 

Raw BOLD image of two co-registered runs, and the signal from the same occipital lobe voxel was not successfully completed. We tried some attempts but it not implementating as it need to implement.