# Resumationator helps tailor your resume to job posts.
#
# Copyright (C) 2022 Jeff Stock <jantonstock@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>

import os
from cold_apply.static.scripts.resume_writer import vars
import time
from datetime import date
import pandas as pd

from fpdf import FPDF
from django.conf import settings


class PDF(FPDF):
    def __init__(self, context: object):
        super().__init__()
        self.person = context['participant'][0]
        self.output_path = f'{settings.MEDIA_ROOT}resumes/{self.person.name}/'
        os.makedirs(self.output_path, exist_ok=True)

    def header(self):
        self.set_font('Arial', 'B', 14)
        self.cell(w=190, h=5, txt=self.person.name, border='B', ln=1, align='C')
        self.set_font('Arial', style='', size=12)
        self.cell(190, 5, f'{self.person.email} | {self.person.phone}', 0, 0, 'C')
        self.ln(10)

    def add_resume_section(self, section_title: str, context: object):
        self.set_font('Times', 'B', size=12)
        self.cell(w=190, h=5, txt=section_title, ln=1, align='C')
        if section_title == 'Overview':
            if len(context['overview']) > 0:
                overview = context['overview'][0].text
            else:
                overview = ''
            self.set_font('Times', size=11)
            self.multi_cell(190, 5, overview, 0, 'J')
            self.ln(4)
        elif section_title == 'Professional Experience':
            exp_count = len(context['experiences'])
            exp_counter = 0
            for exp in context['experiences']:
                exp_counter += 1
                if exp_counter == 4 and exp_counter != exp_count:
                    self.add_page()
                self.set_font('Times', 'B', size=11)
                self.cell(w=100, h=5, txt=exp.position.title, ln=0, align='L')
                start = exp.start_date.strftime('%B %Y')
                if exp.end_date is None:
                    end = 'Present'
                else:
                    end = exp.end_date.strftime('%B %Y')
                exp_dates = f'{start} - {end}'
                self.set_font('Times', 'I', size=11)
                self.cell(w=90, h=5, txt=exp_dates, ln=1, align='R')
                self.set_font('Times', 'I', size=11)
                self.cell(w=100, h=5, txt=exp.org.name, ln=1, align='L')
                self.ln(2)
                for bullet, text in context['weighted_set'].items():
                    if exp.id == bullet:
                        for point in text.values():
                            for t in context['weighted_bullets']:
                                if point['bullet_id'] == t.bullet.id:
                                    self.set_x(15)
                                    self.set_font('Times', size=11)
                                    self.cell(w=5, h=5, txt='·', ln=0, align='L')
                                    self.set_font('Times', size=11)
                                    self.multi_cell(w=175, h=5, txt=t.bullet.text, border=0, align='J')
                                    self.ln(1)
                self.ln(4)
        elif section_title == 'Education':
            ed_count = len(context['education'])
            ed_counter = 0
            for edu in context['education']:
                ed_counter += 1
                formatted = f'{edu.education.degree.abbr} in {edu.education.concentration} - {edu.education.org.name}'
                if ed_count == 1:
                    alignment = 'C'
                    line = 1
                    self.set_font('Times', size=11)
                    self.cell(w=190, h=5, txt=formatted, ln=line, align=alignment)
                    self.ln(2)
                else:
                    if ed_counter % 2 == 0:
                        alignment = 'R'
                        line = 0
                        self.set_font('Times', size=11)
                        self.cell(w=100, h=5, txt=formatted, ln=line, align=alignment)
                    else:
                        alignment = 'L'
                        line = 0
                        self.set_font('Times', size=11)
                        self.cell(w=90, h=5, txt=formatted, ln=line, align=alignment)



    # def footer(self):
    #     self.set_y(-15)
    #     self.set_font('Arial', 'I', 8)
    #     self.cell(0, 10, 'Page ' + str(self.page_no()) + '/{nb}', 0, 0, 'C')


def write_resume(context):
    pdf = PDF(context)
    pdf.alias_nb_pages()
    pdf.add_page()
    pdf.add_resume_section(section_title='Overview', context=context)
    pdf.add_resume_section(section_title='Professional Experience', context=context)
    pdf.add_resume_section(section_title='Education', context=context)

    # TODO: Add skills-first vs chronological order option
    pdf.output(f'{pdf.output_path}{context["job"].company.name}_{context["title"]}.pdf', 'F')

    print('Your .pdf has been created.\nGood bye!\n')
    print("Juandale Pringle Windlebug the III has claimed ownership of this vessel")

    # Juandale Pringle Windlebug the III has claimed ownership of this vessel
