# Resumationator helps tailor your resume to job posts.
# Copyright (C) 2022 Jeff Stock <jantonstock@gmail.com>

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>
import os

def main():
    print('running main')
    # STEP 1
    # Analyze a job description, and show the highest weighted one, two,
    # and three word combinations,
    # so jobseekers can write tailored bdullets
    # upload_resume(input('Enter a filename: '))\
    #  if input('Do you have a new resume to upload (y/n)?') == 'y'\
    #   else 'Okay, no new resume.'


    # jd_text = get_job_post()
    # jd_title = input('Enter a title for the job post text file:\n\t')
    # jd_transcriber(jd_text,jd_title)

    # Path to folder containing job descriptions in .txt format
    # input_path = './input/jds/'


    # Create a useable corpus of words for analysis from the input jds.
    corpus = corpus_prepper(input_path)
    print('Corpus created from job post(s)...')
    # Display key terms in one-, two-, and three-word combinations
    analysis = jd_analyzer(corpus)
    print('Keywords found...')

    # Turn text from JDs into simple corpus that scikit learn uses for
    # count TFIDF
    jd_set = [txt_parser(filename) for filename in corpus]

    #
    # print(current_resume)
    # Make a chart showing keywords
    # chart_token_freq(jd_set)
    # create ordered lists of  each part of spech from job post(s)
    jd_verb_stems = chart_prepper(jd_set,'VERB')[1]
    jd_adj_stems = chart_prepper(jd_set,'ADJ')[1]
    jd_noun_stems = chart_prepper(jd_set,'NOUN')[1]

    # get user input from a .csv file and convert into a pandas
    # data frame
    user_input_filepath = './input/resumes/processed/user_input.csv'
    user_input_df = csv_to_df(user_input_filepath)

    # add lengths of bullets
    user_input_df['bullet_length'] = [bullet_length_comparison(bullet)\
     for bullet in user_input_df['Bullet']]

    user_input_df['parts_of_speech'] = [pos_tagger(bullet)\
     for bullet in user_input_df['Bullet']]

    user_input_df['starts_with_VBN'] = [starts_with_VBN(pos_set)\
     for pos_set in user_input_df['parts_of_speech']]

    # user_input_df['starts_strong'] = [starts_strong(bullet)
    #  for bullet in user_input_df['Bullet']]

    # user_input_df['strong_synonyms'] = [strong_syns(bullet)
    #  for bullet in user_input_df['Bullet']]

    # stem the parts of speech in user input resume bullet statements
    # VERBS
    user_input_df['verb_stems'] =\
     [list(pos_finder(bullet, 'VERB').values())\
      for bullet in user_input_df['Bullet']]

    user_input_df['verb_strength_score'] =\
     [bullet_strength_calculator(stem_list, jd_verb_stems)\
      for stem_list in user_input_df['verb_stems']]

    # ADJ
    user_input_df['adj_stems'] =\
     [list(pos_finder(bullet, 'ADJ').values())\
      for bullet in user_input_df['Bullet']]

    user_input_df['adj_strength_score'] =\
     [bullet_strength_calculator(stem_list, jd_adj_stems)\
      for stem_list in user_input_df['adj_stems']]

    # NOUNS
    user_input_df['noun_stems'] =\
     [list(pos_finder(bullet, 'NOUN').values())\
      for bullet in user_input_df['Bullet']]
    user_input_df['noun_strength_score'] =\
     [bullet_strength_calculator(stem_list, jd_noun_stems)\
      for stem_list in user_input_df['noun_stems']]
    user_input_df['total_bullet_strength'] =\
     (user_input_df['verb_strength_score'] +\
      user_input_df['adj_strength_score'] +\
       user_input_df['noun_strength_score'])

    bullet_strength_index_df =\
     user_input_df[['Bullet','total_bullet_strength']]

    report_check = input('Generate analysis report (y/n)?\n\t')

    if report_check == 'y':
        report_title = input('Enter an analysis report title:\n\t')
        analysis_reporter(analysis, jd_set, report_title)
        print('Analysis report genarated.')

    resume_check = input('Create resume (y/n)?')

    if resume_check == 'y':
        write_resume(user_input_df)

if __name__ == '__main__':
    main()
