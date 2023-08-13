#  -*- coding: utf-8 -*-
__author__ = "kubik.augustyn@post.cz"

from typing import List

import requests
from urllib.parse import urlparse, unquote
from esprima import parseScript
from esprima.nodes import *


class Workaround:
    def __init__(self, url, options):
        self.url = url
        self.parsedUrl = urlparse(url)
        self.options = options

    def start(self) -> bool:
        r = requests.get(str(self.url))
        if r.status_code != 200:
            return False
        ast: Script = parseScript(r.text)
        if not self.__set_options(ast.body[0]):
            return False
        if not self.__set_options(ast.body[1]):
            return False
        un_exp: UnaryExpression = ast.body[2].expression
        if not isinstance(un_exp, UnaryExpression) or un_exp.operator != "~" or not un_exp.prefix:
            return False
        call_exp: CallExpression = un_exp.argument
        if len(call_exp.arguments) > 0:
            return False
        callee: FunctionExpression = call_exp.callee
        params: dict = {}
        for param in callee.params:
            if not isinstance(param, Identifier):
                return False
            params[param.name] = None
        # Don't ask how I got it lol
        string_code = list(map(lambda a: unquote(a), self.__find_function("a", callee.body.body).body
                               .body[0].argument.expressions[0].right.callee.object.value.split("{")
                               ))
        b = self.__find_function("b", callee.body.body)
        string_code_offset = b.body.body[0].argument.expressions[1].right.body.body[0].argument.expressions[
            0].right.right.value
        run_b = lambda a: string_code[a - string_code_offset]

        for_exp: CallExpression = callee.body.body[0].init.expressions[1]
        spec_num = for_exp.arguments[1].value
        while True:
            try:
                # Idk, there must be some JS trick, it doesn't work for me
                if self.__calculate_bin_expression(
                        for_exp.callee.body.body[0].body.block.body[0].test.expressions[0].right,
                        {'parseInt': int, 'i6': run_b}
                ) == spec_num:
                    break
                else:
                    string_code.append(string_code.pop(0))
            except:
                string_code.append(string_code.pop(0))
        pass
        return True

    def __calculate_bin_expression(self, exp: BinaryExpression, funcs: dict) -> float:
        left, right = self.__eval(exp.left, funcs), self.__eval(exp.right, funcs)
        if exp.operator == '+':
            return left + right
        elif exp.operator == '-':
            return left - right
        elif exp.operator == '*':
            return left * right
        elif exp.operator == '/':
            return left / right
        else:
            pass

    def __calculate_unary_expression(self, exp: UnaryExpression, funcs: dict) -> float:
        argument = self.__eval(exp.argument, funcs)
        if exp.operator == '-':
            return -argument
        else:
            pass

    def __eval(self, exp, funcs: dict):
        if isinstance(exp, BinaryExpression):
            return self.__calculate_bin_expression(exp, funcs)
        elif isinstance(exp, UnaryExpression):
            return self.__calculate_unary_expression(exp, funcs)
        elif isinstance(exp, Literal):
            return exp.value
        elif isinstance(exp, CallExpression):
            func = funcs.get(exp.callee.name, print)
            args = list(map(lambda arg: self.__eval(arg, funcs), exp.arguments))
            return func(*args)
        else:
            return None

    def __find_function(self, name: str, pool: list) -> FunctionDeclaration:
        return next(filter(lambda a: isinstance(a, FunctionDeclaration) and a.id.name == name, pool))

    def __set_options(self, statement: ExpressionStatement) -> bool:
        assignment: AssignmentExpression = statement.expression
        if assignment.operator != "=":
            return False
        good, path = self.__get_static_mem_expr_path(assignment.left)
        if not good or len(path) != 3 or path[0] != "window" or path[1] != "_cf_chl_opt":
            return False
        if not isinstance(assignment.right, Literal):
            return False
        self.options[path[2]] = assignment.right.value
        pass
        return True

    def __get_static_mem_expr_path(self, exp: StaticMemberExpression, path=None) -> (bool, List[str]):
        if path is None:
            path = []
        if exp.computed:
            return False, path
        if isinstance(exp.object, StaticMemberExpression):
            if not self.__get_static_mem_expr_path(exp.object, path)[0]:
                return False, path
        elif isinstance(exp.object, Identifier):
            path.append(exp.object.name)
        else:
            return False, path
        path.append(exp.property.name)
        return True, path


if __name__ == '__main__':
    cookie = "uloztoid=1028149561; _pk_id.1.6747=8955b058a467932b.1675013723.; uloztoid2=1028149561; maturity=adult; _nss=1; ULOSESSID=4pdh832s6ibqkfjb1k6bsvfs0m; skin-switcher-selection=light; _gid=GA1.2.632461134.1691915233; adblock_detected=false; _pk_ref.1.6747=%5B%22%22%2C%22%22%2C1691926061%2C%22https%3A%2F%2Fgozofinder.com%2F%22%5D"
    _cf_chl_opt = {
        'cvId': '2',
        'cZone': 'uloz.to',
        'cType': 'managed',
        'cNounce': '13825',
        'cRay': '7f60181acd160b4e',
        'cHash': '887471bc8268c19',
        'cUPMDTk': "\/download-dialog\/free\/download?fileSlug=bETXND2RARAe&__cf_chl_tk=jfyitfysuChk3cbd88zx2uB4DQEdA9xrBAWPaGo2m7Q-1691920649-0-gaNycGzNC3s",
        'cFPWv': 'b',
        'cTTimeMs': '1000',
        'cMTimeMs': '0',
        'cTplV': 5,
        'cTplB': 'cf',
        'cK': "",
        'fa': "/download-dialog/free/download?fileSlug=bETXND2RARAe&amp;__cf_chl_f_tk=jfyitfysuChk3cbd88zx2uB4DQEdA9xrBAWPaGo2m7Q-1691920649-0-gaNycGzNC3s",
        'md': "AHTmzz5whhyQi9xJXui7z6gbLEH3MwA73j.V.z0Ibgk-1691920649-0-AeD1Y3Xa6khp5GcIC_-uI6yiOwaQGCzr-ErES9tcMb3OYBy3gnBfnta2NNXPk_2E36Oqy3A6I4Uhpy0EN2sgChVbzV9cLNn_w0ZEupAetuFKCpzPQGz61eC6x0fvdje9eoWDQ7wkYjMVQ7GkXN6nJ9Olc_wMjo7KOLud6TbA-DvxuaIrGDkea4cRwmjQGBWQayAaMLmUgAWgEg63QTOdiQxrkok3galXoChxivUJlDP5NGFYwh5q7gMByWqBETtFJmdYuAFuP3X5zrzBCl7LSxu35IdL9oquIKIQnTeZ8zFz2Qb-J6FNwgyQDkGl_hxFgGMVHRuttBkHuedfNJjNiy3y30vfuSd1oL85oa70fIWWy66Wh53G0Vv1DLWbQe05SqliLPAS96Oi7jiwTJvy1ad7LbUbtQlRwCZ9M1LvUX_vAZQoJX6NJ0DwUfdItSVoD_yk6qdhjG-7e7HhjZ0eJE34Th4l367AZPqn5ezRM2GMQKOsVjPyyFUPUy7TmOz3s8YmKpQgTtsj6SpB--HCrpytnOBClsStTPBC1F6xxz1NbQxeOYNvUH3nMk381PRjIvTFqiASp78dDV2lggUuTuYGfid6VJI17xqHXTjUU6RlihDRfq2uGOgXnJbnrDkirczZKxFfiu9EazzDpuY95mm5veyiTi2yIAfS1wf0m2XBn95cq-FcONo1vdB36CK4ejYFqChp-J2GTHlYkSjaZ4ONhpBYnd7KtqVx7oru8lrBGYUhbK7Q3qjfOlGjCRwQJf5DCqsOFP6MfmZHNlSUX4QJYcK-Y7Q8oeV7-0vJy337Y3GP1_pznzHBV5Cm5rxo6lOGYqH3aWJl1fQUp5BDiLqcDVu98Gblx4OQc5IZ8LVzpckJiTA75nuCIYKZuF8Jp5cvD49zQcrz0RZShBUi-VfdnEfI-9yF81oRxleqCNpGQb3WD4RYej2Fp2elca-Ci1uzsZGeMTwGbtC1ZPPDi_ILwp3Aniz4rSUJVKcANLue1AnrWJ5SQiSfXJP8Nm5cdTyx6vLOeMnSoBDUJGNkeZbYvuVnd0c4x3TEEqS3aal6LZtAR7h_YGp_9X3XgySKTmFERPvwezp_duF2fopO0M81GnN1DbKuiGf_9dPWj5ssYZC75cCCZKUiAS436ll7PTkjsvsVi8Z7X3uNWrucAbokivHLVdFkMxW4kdsoZYXI34RNkBjma5QuzYUaH7gItSDC9tdAIBt3TQ2oT6AEOrLFKj8U34tVyRBNpDjTbRuLdKsSIR8bBVgtglUv8uicvpLPqkOF5fm0eM20rdVfK_HslzPUraBg2klzWbzCyPUBbQ3mnvM1hcIxMh7c0TWiO7Xg7HtDZzP6P65aJJedPIjDbGe5zITm0q64xGD5ziZjglU3zdBJIt5nJ0x2xaovjqbYQ0iFjCL8OZ7CGBHCt_8zkb8MH4mygHRUVkfh2Wk3tcaDdZ4YQJmGPhxOWvvKb0fsFGx8XjPsJO7QRT3MQRT3xRMbs3V2FYJb4ftGJ-ofUXu07bLObhWXiy_53SZBK_h-A9MFU4BKfXimXfNsy6UZo4_UWI-E40TBmmE10zyrtoctBsYeKn8I0r5KRodO7Fz-jdPDt8bpBBUn8vVXiT6YPFSBQb3GNc-PMAPvbrwv9E4hd6VWOm5UQZU4Y2Ob5EjGS7xA3cBrSp-C5T5IqVn3xEWPniUXREHmDRVsCcZV6Ur-iXxcqEmNeqaRD19nimsewXpVje1wFkqyK4yRSiY1MPg32gwZuA5Vgz_GIEBMBqXnKqqY11rFL_l7vA6wRYU9svxYlrGUmsMEDbyY2PU8_IHAOYknlgpQRrOwPJavJzppGFjR3uS76eCLz6Ky66K5zujJUlzhE4f2baTcBxOYtd5V2hqW1wJfdMSW-AGdgIT5u-ySWk2VZqNjISKdF7ofgQN0DcY7Kv2M-Kbu3FAnj-Vse8Kd_0S0lFrO0xWYI5fyNCHVwHtU__gjIGEdbNbNIVexa2QQZ8WuaclJYqiqpc8Uhj06sXyTq4Z_By_pEB1vYlVAm9UZXRHLmg3JXCWrnCI7SA2SiBW03wyAmFuq52HjYlxVNlKd-Pwtt3WqeV_JfjeDWLoKNeuDXzoXeoav4R4X8PuoYFSS9AcdYz_XxQ8IJsP_VqMQ-Xay6_zJs_Z04IoLHZSa_SrI4AmmfUzDS_CIN3GVfk413uwE1pEYczVi5Q1QtZZQh0Ez8tD2hYq5sOeKROWHAskiQwDW-LfusE_qZ7KLEIFkcP6gQR_efQNvythOJKPpEZcpkCAhXGun6JQOB6pWy_8XGS3FkM8WeTYbVhRBNDFg89ob5y2Bp6jYNYfVEPTPQFVH2QNt_9G2euQ3cBC881CPZ2ELITcQR7MiXricCMSQ-D9vKoJY3MLELj6EXYRb6Ax1xOSsyeO_1xsVxYZTnC1pQJKSpY_EQNU3q6z8BqQW9_c5NZQwvASovbMuXcpmT2PHIQ4TJnYtS2i1-GpC2MAQY0zDwzR6Q_URHFtgdkW9DHhcxnd25hm7vfZrcnmYh-gfwdGVqnfvMHHdPlDZfQA4dyGt5lfbcjtvEjOvVYo2X7H_fvbtJjqHS711wPOmD9bFpF_svA8R4lGnZevw5UR05pqqqOWfsoDz7SSWlayWqiNOoNJal-VCGq-VXOZ_eNYCrJX2rp7pS9Vx9d5tn7AswL32JhlAqmI8kEMrol51IAQnKuBc0-_IjAGzyBFeqcI3ogoSSJ0HSVI6cbHh5phKvJW2wABRkIMI4kCKpFkcPk1mkmVSsnuYPCpkjLMSIf99eZXzq8ENkqz4Y4TUko_c6biIEhIEj_lzm1i4kH_p-DjoRJk7ybdXZbHeSdISXSKwYL8uApm_ZU60nCNMHisFpMn4Mw",
        'cRq': {
            'ru': 'aHR0cHM6Ly91bG96LnRvL2Rvd25sb2FkLWRpYWxvZy9mcmVlL2Rvd25sb2FkP2ZpbGVTbHVnPWJFVFhORDJSQVJBZQ==',
            'ra': 'TW96aWxsYS81LjAgKExpbnV4OyBBbmRyb2lkIDguMS4wOyBTQU1TVU5HIFNNLUc2MTBGIEJ1aWxkL00xQUpRKSBBcHBsZVdlYktpdC81MzcuMzYgKEtIVE1MLCBsaWtlIEdlY2tvKSBTYW1zdW5nQnJvd3Nlci85LjIgQ2hyb21lLzY3LjAuMzM5Ni44NyBNb2JpbGUgU2FmYXJpLzUzNy4zNg==',
            'rm': 'R0VU',
            'd': 'Tgd2Df2agLWxDVS67cza/E3UidYAAQVHyfrOk5Xh/RCOQ3AjEo1ZTWSHkNMxDrl2/MREASb1dV3x0eHW6eci4VXdAlVrZ2I2NT69NP80XnkrB4WSZjKIjVs11KdTP0biK5fUhbP0X+R9D0DpWCIeNgcuL56T5At547rWoZzgL/Pykxekh0nSEtSjs5KZpPZE2LQUOaNBGbHHMZ5JRp8lGLLYeN6vBfn14zHIO0eKd/8ocsmj7UZxa9JLHAutP0AW3G2N8SWn5EXeUHm1NpJn7G443MEbh6wfswaMoBzjlxT0i3D5WXBRXt3YXreSBz1ivUIcxLc05IdQmjjfH2lRuFN1m3Taaazml8JAmOXCIp1iaPqA7lw0DpMYRwfKRYAMhgxcOkHBYqqEFaa54szEb/gQWJ2LPMyYKxXOpysX2UYWyiLQ6gmiuOAcSt4mBMD1wktHkHfqyxEs/Yy2CRtQWkAuYjRIU/obpLmrnpjMFlg=',
            't': 'MTY5MTkyMDY0OS40MTIwMDA=',
            'cT': 1691920651.513000,
            'm': 'PNAqbGfW10Zc33pLP6SzktNBtvVoIEqKzW5Qs14C/pg=',
            'i1': 'wY0JPoZp51LWZmogfEkEfg==',
            'i2': '9Die3lSBYhBEdxl5/bwzGQ==',
            'zh': 'H6H5rT46MdJEduO2EFVWUYu6Mz0W/6o6lKBs5jFOnDc=',
            'uh': 'dsPaLyUsVh0s0KkGEpdF7pFBWQqbk2X0YfTrHj/W7Rc=',
            'hh': 'AZxN1L+Nck6+Yo5cCT418B4s2dJxrgUeCciQcMYDIbA=',
        }
    }
    workaround = Workaround(
        "https://uloz.to/cdn-cgi/challenge-platform/h/b/orchestrate/chl_page/v1?ray=7f60181acd160b4e", _cf_chl_opt)
    if not workaround.start():
        print("Failed!")
