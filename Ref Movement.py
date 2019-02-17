#!/usr/bin/env python
# coding: utf-8

# In[1]:


# Written in python 3
import pywikibot
import re
import mwparserfromhell
import mwparserfromhell.nodes.tag
import pprint
pp = pprint.PrettyPrinter(indent=4)
import pickle
import time


# In[2]:


# Configurations
TEMPLATES_TO_CATER = [
    "infobox medical condition (new)",
    "infobox drug",
    "drugbox"
]


# In[3]:


def find_reference_in_templates_to_be_updated(wikicode, template_flags):
    '''
        Returns: A dictionary object of type: 
            {
                "reference name" : {
                    ref_markup: found in info box 
                    state: 0 = found in box | 1 = found in main | 2 = replaced in main
                    param_object: reference to template parameter
                    template: template name
                    cite_content: the cite content {{cite}}
                }
            }
            
        Args:
            wikicode(mwparserfromhell.wikicode.Wikicode): Parsed wikicode object.
            template_flags(dictionary): template: true|false as per the existance in page
    '''
    ref_map = {}
    for template in wikicode.filter_templates(recursive=False):
        if template.name.strip_code().strip().lower() in template_flags.keys():
            for param in template.params:
                param_value = str(param.value)
                cite_find = re.findall('(<ref name=[^\/>]*>.+<\/ref>)', param_value)
                if len(cite_find) > 0:
                    ref_name_find = re.findall('<ref name=([^\/>]*)>.+<\/ref>', cite_find[0])
                    if len(ref_name_find) > 0 and ref_name_find[0] not in ref_map.keys():
                        cite_content = re.findall('<ref name=[^\/>]*>(.*)<\/ref>', cite_find[0])[0]
                        ref_map[ref_name_find[0]] = {
                            "state": 0,
                            "template": template.name.strip_code().strip().lower(),
                            "param_object": param,
                            "ref_markup": cite_find[0],
                            "cite_content": cite_content
                        }
    
    return ref_map


# In[4]:


def update_wikicode_template_and_body(wikicode, ref_map):
    # update main body
    for node in wikicode.nodes:
        if type(node) == mwparserfromhell.nodes.tag.Tag:
            if node.closing_tag == 'ref' and len(node.attributes) > 0:
                ref_name = node.attributes[0].strip().replace('name=','')
                if ref_name in ref_map.keys() and ref_map[ref_name]["state"] == 0: # not yet replaced
                    node.self_closing = False
                    node.contents = ref_map[ref_name]["cite_content"]
                    ref_map[ref_name]["state"] = 1 #we have found that it needs to be replaced with
    
    #update template
    for ref in ref_map.keys():
        if ref_map[ref]["state"] == 1:
            ref_map[ref]["state"] = 2
            param_value_old = ref_map[ref]["param_object"].value
            ref_tag = '<ref name=' + ref + '/>'
            param_value_new = param_value_old.replace(ref_map[ref]["ref_markup"], ref_tag)
    
    return str(wikicode)


# In[5]:


def move_all_ref_from_infobox_to_body(test_page, pages_parsed_successfully):
    site = pywikibot.Site("en","wikipedia")
    page_name = test_page.title()
    
    print("For page : ", page_name)
    
    if not test_page.exists():
        print("    ERROR: ", page_name, " does not exist")
        raise Exception('The page {} does not exist'.format(page_name))

    wikicode = mwparserfromhell.parse(test_page.text)
    template_flags = { template: False for template in TEMPLATES_TO_CATER }    
    
    for template in wikicode.filter_templates(recursive = False):
        if template.name.strip_code().strip().lower() in template_flags.keys():
            template_flags[template.name.strip_code().strip().lower()] = True;
    
    if True not in template_flags.values():
        print("    No template from TEMPLATES_TO_CATER found")
        pages_parsed_successfully["no_specified_template"].append(page_name)
        return False
    
    ref_map = find_reference_in_templates_to_be_updated(wikicode, template_flags)
    
    if len(ref_map.keys()) < 1:
        print("    No reference found which requires movement")
        pages_parsed_successfully["no_ref_movement_required"].append(page_name)
        return False
    else:
        modified_wikitext = update_wikicode_template_and_body(wikicode, ref_map)
        if modified_wikitext != test_page.text:
            print("    References need to be moved")
#             print("="*15);
#             print(test_page.text)
#             print("="*15);
#             print(modified_wikitext)
#             print("="*15);
            test_page.text = modified_wikitext
            test_page.save(summary='Moving Reference(s) out of Infobox', minor=True, botflag=True)
            print("    *** Updating the page")
            pages_parsed_successfully["updated"].append(page_name)
            return True
        else:
            print("    No reference can be moved")
            pages_parsed_successfully["no_corressponding_ref_found"].append(page_name)
            return False


# In[6]:


################################## MAIN ####################################

# Prepare for bot run metrics
pages_error = [] # array of dict {
# "name" :
# "error" : err_obj
#}
pages_parsed_successfully = {
    "updated" : [],
    "no_specified_template": [],
    "no_ref_movement_required": [],
    "no_corressponding_ref_found": []
}
category_on_which_bot_needs_to_run = 'RTT'


# In[7]:


# Collect pages where bot needs to be run
site = pywikibot.Site("en","wikipedia")
category_list_page = pywikibot.Category(site, category_on_which_bot_needs_to_run)


# In[8]:


# Run the bot
target_count = 0
for target_page in category_list_page.articles(recurse=True):
    target_count += 1
    print("Processing target : ", target_count)
    try:
        move_all_ref_from_infobox_to_body(target_page, pages_parsed_successfully)
    except Exception as e:
        print("Exception occured ", str(e))
        pages_error.append({
            "name" : str(target_page),
            "error" : e  
        })
    time.sleep(1)


# In[9]:


print("Ran on ", target_count," pages")


# In[10]:


result_report = {
    "pages_parsed_successfully" : pages_parsed_successfully,
    "pages_error" : pages_error
}


# In[11]:


with open('bot_run_results.pickle', 'wb') as handle:
    pickle.dump(result_report, handle, protocol=pickle.HIGHEST_PROTOCOL)


# In[12]:


# Reading result pickle file
# with open('bot_run_results.pickle', 'rb') as handle:
#     result_report = pickle.load(handle)


# In[13]:


print("Count of Pages faced error: ", len(result_report["pages_error"]))
print("Count of updated Pages: ", len(result_report["pages_parsed_successfully"]["updated"]))
print("Count of Pages where target template not found: ", len(result_report["pages_parsed_successfully"]["no_specified_template"]))
print("Count of Pages where no refs with name in info box: ", len(result_report["pages_parsed_successfully"]["no_ref_movement_required"]))
print("Count of Pages where no corresponding refs in main body found: ", len(result_report["pages_parsed_successfully"]["no_corressponding_ref_found"]))


# In[ ]:




