.PHONY: test docs run
test:
	python3 -m unittest discover -s scheduler_sim/tests -p "tests_unittest.py" -v

docs:
	@echo "Compile LaTeX (requires pdflatex installed locally)."
	@echo "cd scheduler_sim/docs/latex && pdflatex main.tex && pdflatex main.tex"

run:
	python3 -m scheduler_sim.cli --config scheduler_sim/data/caso.txt --mode full --outdir scheduler_sim/out
