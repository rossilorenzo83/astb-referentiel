"""Frozenset of common French first names, used to resolve all-titlecase
name ambiguity (LASTNAME Firstname vs Firstname LASTNAME order).

This list is not exhaustive — it only needs to cover enough of the
"common" distribution to disambiguate typical doctor records. When one of
two words in a titlecase name is recognized here and the other isn't, we
can confidently assign them.
"""

import unicodedata


def _normalize(name: str) -> str:
    """Lowercase, accent-stripped, hyphens/spaces collapsed for lookup."""
    if not name:
        return ""
    s = unicodedata.normalize("NFD", name)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return s.lower().replace("-", "").replace(" ", "").strip()


_RAW_NAMES = """
Adrien Agathe Alain Alban Albane Alexandra Alexandre Alexis Alice Aline Alix
Amandine Ambre Amelie Anais Andre Andrea Angele Angelique Anna Anne Annie
Annick Anthony Antoine Antonin Antoinette Apolline Aramis Ariane Arnaud
Arthur Auguste Augustin Aurelie Aurelien Aurore Axel Axelle Baptiste Barbara
Bastien Beatrice Benjamin Benoit Bernadette Bernard Bertrand Blanche Boris
Brice Brigitte Bruno Camille Capucine Carine Carla Carole Caroline Catherine
Cecile Cedric Celia Celine Celeste Chantal Charles Charlie Charline Charlotte
Chloe Christelle Christian Christiane Christine Christophe Claire Claude
Claudine Clelia Clement Clementine Clotilde Colette Colin Come Constance
Constant Corentin Corinne Cyril Cyrille Damien Daniel Daniele Danielle
David Delphine Denis Denise Diane Didier Dimitri Dominique Dorothee Edgard
Edith Edmond Edouard Eleonore Elena Eliane Elie Eliott Elisa Elisabeth
Elise Ellen Elodie Eloi Eloise Elsa Emile Emilie Emilien Emma Emmanuel
Emmanuelle Enora Eric Erika Ernest Estelle Esteban Esther Etienne Eugene
Eugenie Eva Evan Eve Evelyne Fabien Fabienne Fabrice Fanny Felicie Felix
Ferdinand Fernand Fernande Fiona Flavie Flavien Fleur Flore Florence
Florent Florentin Florian Florine Francis Francois Francoise Frederic
Frederique Gabriel Gabrielle Gael Gaelle Gaetan Garance Gaspard Gaston
Gautier Genevieve Geoffrey Geoffroy Georges Gerald Geraldine Gerard
Germaine Ghislaine Gilbert Gilberte Gilles Ginette Gisele Gilles Giovanni
Gregory Gregoire Guillaume Guillemette Guy Guylaine Gwenaelle Hadrien
Hanna Harold Helene Henri Henriette Herve Hippolyte Honore Hortense
Hugo Hugues Ianis Igor Ines Ingrid Irene Iris Isaac Isabelle Isaure Ismail
Jacinthe Jack Jacob Jacqueline Jacques Jade James Jason Jean Jeanne
Jeannette Jeannine Jennifer Jeremie Jeremy Jerome Jessica Joachim Jocelyn
Jocelyne Joel Joelle Johan Johanne John Joseph Josephine Josette Josiane
Josua Judith Julia Julie Julien Juliette Justine Karl Karine Katell
Katia Kevin Killian Laeticia Laetitia Laurane Laure Laurence
Laurent Laurie Lea Leandre Leila Leo Leon Leonard Leonie Leopold Leslie
Lia Liam Lili Lilian Liliane Lilou Linda Lisa Lise Lisette Livia Loic
Lola Lorenzo Lorraine Louis Louisa Louise Louna Lubin Luc Luca Lucas
Lucie Lucien Lucienne Ludivine Ludovic Luna Lydia Lydie Mael Maelle
Magali Magdalena Maia Maitena Manon Marc Marceau Marcel Marceline Marcelle
Margaux Margot Marguerite Maria Mariam Marianne Marie Mariette Marilyn
Marin Marina Marine Marion Marius Marjorie Martial Martine Marvin
Mary Maryline Maryse Mathieu Mathilde Mathias Mathis Mathurin Mathys
Matteo Mattheo Maud Maude Maurice Maxence Maxime Maximilien Melanie
Melina Meline Melissa Melodie Michael Michel Michele Micheline Michelle
Miguel Milan Mila Milo Mireille Mohamed Monique Morgan Morgane Muriel
Myriam Nadege Nadia Nadine Nancy Naomi Nathalie Nathan Nathaniel Nelly
Nestor Nicolas Nicole Nils Noa Noah Noe Noelie Noelle Noemie Nolan
Norbert Norma Norman Octave Odette Odile Olga Olivia Olivier Ombeline
Ophelie Oscar Oswald Owen Pablo Paola Pascal Pascale Patricia Patrice
Patrick Paul Paule Paulette Pauline Perrine Peter Philemon Philippe
Philippine Pierre Pierrette Pierrick Prune Quentin Rachel Raphael Raphaelle
Raoul Raymond Raymonde Rebecca Regine Remi Remy Renaud Rene Renee Rita
Robert Roberte Robin Roch Rodolphe Rodrigue Roger Roland Romain Romane
Romeo Rosalie Rose Roseline Sabine Sabrina Salome Samira Samuel Sandra
Sandrine Sarah Sasha Sebastien Segolene Serge Severine Side Sidonie
Silvain Silvie Simon Simone Solange Soline Solene Sonia Sophie Stephane
Stephanie Steven Suzanne Suzie Sybille Sylvain Sylvette Sylvie Tanguy
Tania Tatiana Thais Thao Thea Theo Theodore Theophane Theophile Therese
Thibault Thibaut Thierry Thomas Tiago Timothe Timothee Titouan Tom Tony
Tristan Ulysse Ugo Valentin Valentine Valeria Valerie Valery Vanessa
Vera Veronique Victor Victoire Victoria Viktor Vincent Violette Virginie
Vivien Vladimir Walid Wendy William Xavier Yann Yanis Yannick Yasmine
Yolande Yves Yvette Yvon Yvonne Zelie Zoe
"""


FRENCH_FIRST_NAMES: frozenset[str] = frozenset(
    _normalize(n) for n in _RAW_NAMES.split() if n
)


def is_french_first_name(word: str) -> bool:
    """True if the word matches a common French first name, any case.

    Hyphenated compounds ('Jean-Pierre', 'Marie-Claire') are accepted when
    each component is itself a known first name.
    """
    if not word:
        return False
    if _normalize(word) in FRENCH_FIRST_NAMES:
        return True
    # Hyphenated compound: every component must be a known first name
    parts = [p for p in word.replace(" ", "-").split("-") if p]
    if len(parts) > 1 and all(_normalize(p) in FRENCH_FIRST_NAMES for p in parts):
        return True
    return False
